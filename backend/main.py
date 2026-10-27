
import os
import logging
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client


# --------------------------------------------------
# Application setup
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meridian-call-guide")

app = FastAPI(
    title="Meridian Call Guide API",
    version="1.0.0"
)

origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5173"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(origins + [
        "http://127.0.0.1:5173"
    ])),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Database connection
# --------------------------------------------------

def db() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Backend database is not configured. "
                "Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY."
            )
        )

    return create_client(url, key)


# --------------------------------------------------
# Request models
# --------------------------------------------------

class StartCall(BaseModel):
    prospect_name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=160)
    prospect_role: str = Field(default="", max_length=160)


class StageResult(BaseModel):
    stage_number: int = Field(ge=1, le=8)
    result_code: str = Field(min_length=1, max_length=80)
    prospect_words: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=1000)


class CloseCall(BaseModel):
    outcome: str = Field(min_length=1, max_length=80)
    next_step: str = Field(default="", max_length=1000)
    prospect_need_words: str = Field(default="", max_length=4000)


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "meridian-call-guide-api",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# --------------------------------------------------
# Call stages
# --------------------------------------------------

@app.get("/stages")
def list_stages():
    try:
        return (
            db()
            .table("call_stages")
            .select(
                "stage_number,name,purpose,prospect_phrases"
            )
            .order("stage_number")
            .execute()
            .data
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Could not load stages")
        raise HTTPException(
            status_code=502,
            detail=f"Could not load stages: {str(e)}"
        )


# --------------------------------------------------
# Start a call
# --------------------------------------------------

@app.post("/calls", status_code=201)
def start_call(payload: StartCall):
    try:
        rows = (
            db()
            .table("calls")
            .insert({
                "prospect_name": payload.prospect_name.strip(),
                "company_name": payload.company_name.strip(),
                "prospect_role": payload.prospect_role.strip(),
                "last_stage": 1
            })
            .execute()
            .data
        )

        if not rows:
            raise HTTPException(
                status_code=502,
                detail="Call could not be created."
            )

        return rows[0]

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Could not start call")
        raise HTTPException(
            status_code=502,
            detail=f"Could not start call: {str(e)}"
        )


# --------------------------------------------------
# Save a stage result
# --------------------------------------------------

@app.post("/calls/{call_id}/stage-results")
def save_stage_result(call_id: str, payload: StageResult):
    try:
        client = db()

        found = (
            client.table("calls")
            .select("id,last_stage,ended_at")
            .eq("id", call_id)
            .maybe_single()
            .execute()
            .data
        )

        if not found:
            raise HTTPException(
                status_code=404,
                detail="Call not found."
            )

        if found.get("ended_at"):
            raise HTTPException(
                status_code=409,
                detail="This call is already closed."
            )

        result = {
            "call_id": call_id,
            **payload.model_dump()
        }

        saved = (
            client.table("call_stage_results")
            .upsert(
                result,
                on_conflict="call_id,stage_number"
            )
            .execute()
            .data
        )

        call_update = {
            "last_stage": payload.stage_number
        }

        if payload.stage_number == 5 and payload.prospect_words:
            call_update["prospect_need_words"] = (
                payload.prospect_words
            )

        (
            client.table("calls")
            .update(call_update)
            .eq("id", call_id)
            .execute()
        )

        return saved[0] if saved else result

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Could not save stage result")
        raise HTTPException(
            status_code=502,
            detail=f"Could not save stage result: {str(e)}"
        )


# --------------------------------------------------
# Generate an AI summary using Gemini
# --------------------------------------------------

def generate_ai_summary(client: Client, call_id: str, call_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured.")
        return ""

    try:
        stages = (
            client.table("call_stage_results")
            .select(
                "stage_number,result_code,prospect_words,notes"
            )
            .eq("call_id", call_id)
            .order("stage_number")
            .execute()
            .data
        )

        summary_input = {
            "prospect": {
                "prospect_name": call_data.get("prospect_name"),
                "company_name": call_data.get("company_name"),
                "prospect_role": call_data.get("prospect_role"),
                "outcome": call_data.get("outcome"),
                "next_step": call_data.get("next_step"),
                "prospect_need_words": call_data.get(
                    "prospect_need_words"
                ),
            },
            "stage_results": stages
        }

        summary_prompt = (
            "Write a factual, concise, two-sentence cold-call CRM "
            "summary. Use only the supplied data. Do not invent "
            "facts or infer details that are not present. Preserve "
            "the prospect's exact words when quoting. Mention the "
            "call outcome and next step when available.\n\n"
            f"Call data: {summary_input}"
        )

        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/gemini-3.6-flash:generateContent"
        )

        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": summary_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 180
            }
        }

        with httpx.Client(timeout=20.0) as http_client:
            response = http_client.post(
                url,
                params={"key": api_key},
                json=request_body
            )

        # Log the reason if Gemini rejects the request.
        if not response.is_success:
            logger.error(
                "Gemini API returned HTTP %s: %s",
                response.status_code,
                response.text[:1000]
            )
            return ""

        data = response.json()
        candidates = data.get("candidates", [])

        if not candidates:
            logger.warning(
                "Gemini returned no candidates. Response keys: %s",
                list(data.keys())
            )
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])

        summary = " ".join(
            part.get("text", "").strip()
            for part in parts
            if part.get("text", "").strip()
        ).strip()

        if not summary:
            logger.warning("Gemini returned an empty summary.")
            return ""

        # Save the generated summary in Supabase.
        (
            client.table("calls")
            .update({"ai_summary": summary})
            .eq("id", call_id)
            .execute()
        )

        logger.info("AI summary generated and saved for call %s", call_id)
        return summary

    except Exception:
        logger.exception("Gemini summary generation failed")
        return ""


# --------------------------------------------------
# Close a call
# --------------------------------------------------

@app.post("/calls/{call_id}/close")
def close_call(call_id: str, payload: CloseCall):
    try:
        client = db()

        found = (
            client.table("calls")
            .select("id,last_stage,ended_at")
            .eq("id", call_id)
            .maybe_single()
            .execute()
            .data
        )

        if not found:
            raise HTTPException(
                status_code=404,
                detail="Call not found."
            )

        if found.get("ended_at"):
            raise HTTPException(
                status_code=409,
                detail="This call is already closed."
            )

        words = payload.prospect_need_words.strip()

        call_update = {
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "outcome": payload.outcome,
            "next_step": payload.next_step.strip()
        }

        if words:
            call_update["prospect_need_words"] = words

        updated = (
            client.table("calls")
            .update(call_update)
            .eq("id", call_id)
            .execute()
            .data
        )

        if not updated:
            raise HTTPException(
                status_code=502,
                detail="Call could not be closed."
            )

        call_data = updated[0]

        # The call is already saved, even if Gemini fails.
        summary = generate_ai_summary(
            client,
            call_id,
            call_data
        )

        return {
            **call_data,
            "ai_summary": summary,
            "llm_note": (
                "Summary generated"
                if summary
                else (
                    "Call saved; AI summary unavailable. "
                    "Check the backend terminal for the Gemini error."
                )
            )
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Could not close call")
        raise HTTPException(
            status_code=502,
            detail=f"Could not close call: {str(e)}"
        )


# --------------------------------------------------
# Call history
# --------------------------------------------------

@app.get("/calls")
def get_calls(limit: int = 100):
    try:
        safe_limit = min(max(limit, 1), 200)

        return (
            db()
            .table("calls")
            .select(
                "id,prospect_name,company_name,prospect_role,"
                "started_at,ended_at,last_stage,outcome,next_step,"
                "prospect_need_words,ai_summary"
            )
            .order("started_at", desc=True)
            .limit(safe_limit)
            .execute()
            .data
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Could not list calls")
        raise HTTPException(
            status_code=502,
            detail=f"Could not list calls: {str(e)}"
        )


# --------------------------------------------------
# Individual call details
# --------------------------------------------------

@app.get("/calls/{call_id}")
def get_call(call_id: str):
    try:
        client = db()

        call = (
            client.table("calls")
            .select("*")
            .eq("id", call_id)
            .maybe_single()
            .execute()
            .data
        )

        if not call:
            raise HTTPException(
                status_code=404,
                detail="Call not found."
            )

        stages = (
            client.table("call_stage_results")
            .select("*")
            .eq("call_id", call_id)
            .order("stage_number")
            .execute()
            .data
        )

        return {
            "call": call,
            "stage_results": stages
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Could not retrieve call")
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve call: {str(e)}"
        )
