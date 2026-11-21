# Adding companion code for a blog post

This repository holds companion code for published articles, kept separate
from actively maintained project repositories.

If a tool or library is meant to be actively maintained, versioned for users,
or accept external issues, give it its own repository instead.

## 1. Create a post folder

Add a new top-level directory named `YYYY-MM-short-slug/`, for example
`2026-11-pdf-parsing/`.

**Do not rename a folder after publication** — published articles link to
`tree/main/<folder>`.

Each post folder should be self-contained:

- `README.md` with:
  - what the code does and how to run it,
  - the published article URL (add it once the article is live),
  - a short notice that the code is provided as-is to reproduce the article
    and is not actively maintained.
- Pinned dependencies (`uv.lock`, `requirements.txt`, `renv.lock`, etc.) so
  the exact tested environment is documented.
- `LICENSE` / `NOTICE` if the post uses a license other than the repo's
  default Apache-2.0 or bundles third-party code, fonts, or data.

## 2. Keep the repository lightweight

Aim to keep each post folder **under ~10 MB**. Do not commit model weights,
large datasets, rendered videos, or build artefacts — host large assets on
Zenodo or Hugging Face and link to them from the folder's `README.md`.

## 3. Open a pull request

Add a row to the table in the root [`README.md`](README.md) and open a PR to
`main`. Before merging, a reviewer checks:

- no secrets, tokens, or internal/unpublished data,
- third-party code/data/fonts carry the required license notices,
- no oversized binaries,
- the folder's `README.md` explains how to run the code.

## 4. Publish the downloadable ZIP

After your PR is merged, create a Release ZIP for that folder in either of
two ways:

- **From the GitHub UI (easiest):** Go to **Actions → Release post zip →
  Run workflow**, enter the folder name (e.g. `2026-11-pdf-parsing`) and
  version (`v1`), and click **Run workflow**.
- **From git:**

```bash
git tag 2026-11-pdf-parsing/v1
git push origin 2026-11-pdf-parsing/v1
```

This creates a GitHub Release with `<folder>.zip` attached (including
`LICENSE`).

## 5. Handing off to the press team

Give the press team the stable folder URL on `main`:

```text
https://github.com/basillicus/blog-companions/tree/main/YYYY-MM-short-slug
```

Once the release exists, add a direct ZIP download link at the top of your
folder's `README.md` (pointing to the specific release tag, not
`releases/latest`). That way you can fix typos, add the live article link, or
cut a `v2` ZIP without needing the press team to edit the article.
