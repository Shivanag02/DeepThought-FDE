# Deployment and submission checklist

- [ ] Run `supabase/schema.sql` in Supabase SQL Editor.
- [ ] Set backend environment variables locally; never commit `.env`.
- [ ] Start backend and verify `/health`.
- [ ] Start frontend and create a test call.
- [ ] Save results for at least two stages; test stage 5 exact words.
- [ ] End call and verify it appears in history with stage reached and outcome.
- [ ] Configure Gemini API key on backend and verify an AI summary; app must still save calls if AI summary is unavailable.
- [ ] Push repository publicly to GitHub.
- [ ] Deploy backend to Render and confirm public `/health` URL returns JSON.
- [ ] Deploy frontend to Vercel and confirm API requests work.
- [ ] Add URLs and chosen LLM use to README.
- [ ] Record a 6+ minute video with your camera visible, walking through one transcript and explaining one design decision.
- [ ] Upload video to Google Drive and set access to Anyone with the link can view.
- [ ] Open the video link in a private/incognito window to verify access.
- [ ] Send repository, Vercel URL, Render health URL and video link as required by the task.
