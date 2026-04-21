# Prep Support Portal (Headless GitHub)

This is a Next.js application that serves as the specialized support portal for Prep (`support.runprep.io`).

It uses a **Headless GitHub** architecture:
- **Frontend**: Custom Next.js UI using `@prep/ui` components.
- **Backend**: GitHub Discussions API (GraphQL) serves as the CMS.
- **Interaction**: Read-only view of discussions; interactions (reply/post) redirect to GitHub.

## Setup

1. Copy the environment example:
   ```bash
   cp .env.local.example .env.local
   ```

2. Generate a GitHub Personal Access Token (Fine-grained):
   - **Permissions**: Read-only access to "Discussions" and "Metadata" for the repo.
   - **Repository**: `MagneticAnomaly/RunPrep` (or your target repo).

3. Add the token to `.env.local`:
   ```bash
   GITHUB_TOKEN=github_pat_...
   ```

4. Run the development server:
   ```bash
   turbo dev --filter=@prep/support
   ```
   (Runs on http://localhost:3002)

## Features

- **Troubleshooting & Quick Links**: Cards linking to Docs, Payments, and Email.
- **Community Feed**: Live feed of recent GitHub Discussions fetched via GraphQL.
- **Server-Side Rendering**: Fast initial load with ISR (Incremental Static Regeneration) caching (60s).
