# Third-party files served by the app

Copied here (10/11/2026) so the page needs no other site: local mode opens
with its full look with no internet, and no script from someone else's server
runs in a logged-in session. The Content-Security-Policy (`app/main.py`) only
allows scripts, styles and fonts from the app itself, and `tests/test_app.py`
fails if `web/index.html` loads anything from another site.

| Here | Source | License |
|---|---|---|
| `tailwindcss/tailwind-3.4.17.js` | `https://cdn.tailwindcss.com/3.4.17` — Tailwind CSS v3.4.17, the Play CDN build (generates the CSS in the browser, no build step) | MIT — `tailwindcss/LICENSE` |
| `saira-condensed/*.woff2` | `https://fonts.gstatic.com/s/sairacondensed/v12/` — Saira Condensed from Google Fonts, weights 500/600/700, subsets latin, latin-ext and vietnamese | SIL Open Font License 1.1 — `saira-condensed/OFL.txt` |

`saira-condensed.css` is ours: the `@font-face` rules for those files, with the
same unicode ranges Google Fonts uses (the browser only fetches the subsets a
page's text needs).

The downloaded files are byte-for-byte what the source served — never edit
them. To update one: download the new version next to the old one **under a
new file name** (keep the version in it), point `web/index.html` (or
`saira-condensed.css`) at it, update this file and delete the old one. The new
name matters: the app tells browsers to keep everything in the folders here
for a year (`NoCacheStaticFiles` in `app/main.py`), so a changed file under an
old name would not reach anyone who already has it.

## SHA-256

Of the files as downloaded. The text ones have LF line endings; a Windows
checkout with `core.autocrlf` rewrites them, which changes the hash but not
what they do.

| File | Name at the source | SHA-256 |
|---|---|---|
| `tailwindcss/tailwind-3.4.17.js` | `3.4.17` | `176e894661aa9cdc9a5cba6c720044cbbf7b8bd80d1c9a142a7c24b1b6c50d15` |
| `tailwindcss/LICENSE` | `LICENSE` at tag `v3.4.17` of `github.com/tailwindlabs/tailwindcss` | `60e0b68c0f35c078eef3a5d29419d0b03ff84ec1df9c3f9d6e39a519a5ae7985` |
| `saira-condensed/saira-condensed-500-latin.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnUchQ962f.woff2` | `22c6c5bf5a71e10f0d0f71f630414437797738ed8aef613c457c749498b5e783` |
| `saira-condensed/saira-condensed-500-latin-ext.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnUchQ-a2fli0.woff2` | `da5cf8e6bb5d0632afe50eb44574f7614be6c64023389b0e39d44d47668b7436` |
| `saira-condensed/saira-condensed-500-vietnamese.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnUchQ-K2fli0.woff2` | `76fbc9b594287a99bd9ed642c0a82f93810be7166ddc53d24c85020fa69b2877` |
| `saira-condensed/saira-condensed-600-latin.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnfc9Q962f.woff2` | `d20f5b8d2d6a1a236cf776fa3ac0bec671503824cbed5dedf656b61930dc87ee` |
| `saira-condensed/saira-condensed-600-latin-ext.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnfc9Q-a2fli0.woff2` | `0bf20d8abc9843a3039af6c678237d795ac09fa3695cfeaa8e29be246bfed6c6` |
| `saira-condensed/saira-condensed-600-vietnamese.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnfc9Q-K2fli0.woff2` | `2931c3c60d0528eaac1fbfaf4f79d732cc9a6f11b98a986bb944624ecc7eaa0a` |
| `saira-condensed/saira-condensed-700-latin.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnGc5Q962f.woff2` | `eb1cf59a1f785a890ac30d69bb59fffef3989fef4e7a2ae2367c85e861077fda` |
| `saira-condensed/saira-condensed-700-latin-ext.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnGc5Q-a2fli0.woff2` | `f15c9a22d2d8f00bebdf7f005f95b75e502813de13ad70879a5c8bba65d6f4ea` |
| `saira-condensed/saira-condensed-700-vietnamese.woff2` | `EJRLQgErUN8XuHNEtX81i9TmEkrnGc5Q-K2fli0.woff2` | `6a2fca4aa8a71fed4254ab314eec335574ce011bb66d09db146ec676cb57190f` |
| `saira-condensed/OFL.txt` | `ofl/sairacondensed/OFL.txt` of `github.com/google/fonts` | `0e2ccc5da1dd979f08ba82bca2fb61592506a1e58d3cbfc26d904f0db71bd812` |
