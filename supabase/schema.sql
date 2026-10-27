-- Meridian Call Guide: run this entire file in Supabase SQL Editor.
create extension if not exists pgcrypto;

create table if not exists public.call_stages (
  stage_number integer primary key check (stage_number between 1 and 8),
  name text not null,
  purpose text not null,
  prospect_phrases jsonb not null default '[]'::jsonb
);

insert into public.call_stages (stage_number, name, purpose, prospect_phrases) values
(1, 'Opening', 'Reach the right person and say who you are.', '["Who is calling?", "I am in a meeting right now.", "You have the wrong number."]'::jsonb),
(2, 'Purpose', 'Explain in one or two sentences why you called, in words they can repeat.', '["From where? Can you say it again?", "What is this regarding?", "Is this a sales call?"]'::jsonb),
(3, 'Permission', 'Get a clear yes, a no, or a specific time to call back.', '["Call me after 30 minutes.", "I am busy right now.", "Okay, go ahead."]'::jsonb),
(4, 'Their business', 'Ask about their company and work before explaining your offer.', '["We work in a different division.", "Tell me about your company first.", "We are a startup; this may not be relevant."]'::jsonb),
(5, 'Their need', 'Capture the prospect’s need in their own words, without paraphrasing it.', '["We want to enter a new market.", "Everything is fine; we do not need anything.", "What can you do for a company like ours?"]'::jsonb),
(6, 'Objection', 'Understand the reason for resistance before responding.', '["We already have a consultant.", "I am not the right person.", "Send something in writing and we will see."]'::jsonb),
(7, 'Next step', 'Agree one concrete next action, with a time or channel.', '["Send it on WhatsApp.", "Call me Tuesday after 2 PM.", "Speak to my colleague."]'::jsonb),
(8, 'Close', 'End clearly and record the outcome, next step, and prospect’s words.', '["Thank you, goodbye.", "I am not interested.", "The line dropped."]'::jsonb)
on conflict (stage_number) do update set name=excluded.name, purpose=excluded.purpose, prospect_phrases=excluded.prospect_phrases;

create table if not exists public.calls (
  id uuid primary key default gen_random_uuid(),
  prospect_name text not null,
  company_name text not null,
  prospect_role text,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  last_stage integer not null default 1 check (last_stage between 1 and 8),
  outcome text,
  next_step text,
  prospect_need_words text,
  ai_summary text,
  created_at timestamptz not null default now()
);

create table if not exists public.call_stage_results (
  id uuid primary key default gen_random_uuid(),
  call_id uuid not null references public.calls(id) on delete cascade,
  stage_number integer not null references public.call_stages(stage_number),
  result_code text not null,
  prospect_words text not null default '',
  notes text not null default '',
  created_at timestamptz not null default now(),
  unique (call_id, stage_number)
);

create index if not exists idx_calls_started_at on public.calls (started_at desc);
create index if not exists idx_stage_results_call_id on public.call_stage_results (call_id);

-- This MVP uses the Supabase service-role key only in the Render backend.
-- Never place the service-role key in Vercel/frontend environment variables.
