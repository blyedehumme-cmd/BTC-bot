# Lesly Frontend

Premium landing page and dashboard UI for Lesly AI Trading.

## Run locally

1. Open a terminal in `lesly-frontend`
2. Install dependencies:

```bash
npm install
```

3. Start development server:

```bash
npm run dev
```

4. Open `http://localhost:3000`

## Backend integration

- Set `NEXT_PUBLIC_BACKEND_URL` in `lesly-frontend/.env` or use the provided `.env.example`.
- The UI fetches data from the backend API at `http://localhost:8000/api` by default.

## Notes

- Paper-trading UI only. No real orders.
- Built with Next.js, React and Tailwind CSS.

## Deploy to Vercel

1. Import this repository into Vercel.
2. Use `lesly-frontend` as the project root or configure `rootDirectory: "lesly-frontend"`.
3. Set the Vercel environment variable:
   - `NEXT_PUBLIC_BACKEND_URL=https://<YOUR_BACKEND_HOST>/api`
4. Deploy and open the generated public URL.
