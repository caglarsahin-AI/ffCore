# frontend

Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui, next-intl (tek dil `tr`), next-themes.
Host'a Node kurulmaz; tüm npm komutları konteynerde (docs/gelistirme-ortami.md):

```bash
docker compose build frontend
docker compose run --rm frontend npm run lint
```

- Türkçe metinler yalnızca `messages/tr.json`; kodda sabit Türkçe metin yok.
- Tema token'ları `styles/tokens.css` (açık `:root`, koyu `.dark`); bileşenlerde sabit renk yok.
