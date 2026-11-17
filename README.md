# World Sports Hub
A mobile-first static sports news site with a scheduled RSS -> Gemini summary -> Supabase publishing pipeline.

## What this starter does
- Collects sports headlines from Google News RSS topic searches.
- Uses Gemini to write short, cautious summaries based only on supplied RSS metadata.
- Stores/upserts articles in Supabase; source links are preserved.
- Publishes the site as static files on Cloudflare Pages.
- Runs once daily at 09:15 East Africa Time through GitHub Actions, plus manual runs.

## Important limitations
- This is an automated news discovery and summary site, not a live sports broadcaster.
- Do not upload or rebroadcast EPL/other protected match footage without a licence. Only embed videos where the publisher permits embedding.
- RSS feeds, APIs, Gemini free quotas and hosting quotas can change. A free tier is not an unlimited production guarantee.
- Automated summaries can be wrong. Keep source links visible and review breaking, legal, injury and transfer claims. For stronger verification, add a second independent source before labelling something confirmed.
- Google News RSS is an aggregation feed; the source URL may be a Google News redirect. The original publisher/source name is retained where supplied.

## Setup
1. Create a Supabase project. In SQL Editor, run `sql/schema.sql`.
2. In Supabase Project Settings > API, copy Project URL, anon/public key, and service_role key. Never put service_role in frontend code or commit it to GitHub.
3. In `app.js`, replace `PASTE_YOUR_SUPABASE_PROJECT_URL_HERE` and `PASTE_YOUR_SUPABASE_ANON_KEY_HERE` with the Project URL and anon/public key. The table has public SELECT-only RLS.
4. Create a Gemini API key in Google AI Studio.
5. Push this folder to a GitHub repository.
6. In GitHub repository Settings > Secrets and variables > Actions, add secrets:
   - `SUPABASE_URL` = Supabase Project URL
   - `SUPABASE_SERVICE_ROLE_KEY` = service_role key (secret)
   - `GEMINI_API_KEY` = Gemini API key (secret)
7. In GitHub, open Actions > Daily sports news automation > Run workflow. Check the log. Then check Supabase Table Editor > articles.
8. Deploy to Cloudflare Pages: Workers & Pages > Create > Pages > Connect to Git > select repository. Framework preset: None; build command blank; output directory `.` (the repository root). Deploy.
9. Open the assigned `*.pages.dev` URL. It should load the stories after the first successful automation run.

## Android workflow
Use Chrome to create accounts, edit files in GitHub's web editor, run Actions, and deploy from Cloudflare's dashboard. No computer or Android app install is required. For editing multiple files, GitHub's web UI or an Android code editor is easier than editing a large file in one browser textbox.

## Troubleshooting
- Website says Setup required: check the two public values in `app.js`.
- No articles: run the workflow manually and inspect its logs. Verify all three GitHub Actions secrets.
- Supabase 401/403: confirm SQL ran successfully and the frontend uses the anon/public key, not service_role.
- Gemini 429: free quota reached; wait for quota reset or reduce `MAX_PER_FEED`.
- Duplicate items: source_url is unique and the workflow upserts, so repeat runs update rather than duplicate the same URL.
