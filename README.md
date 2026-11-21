# Blog companion code

Code, demo inputs, notebooks, and evaluation scripts accompanying our
published blog posts. Each folder corresponds to one article.

> **Support & maintenance:** Each folder is a snapshot provided **as-is** to
> reproduce the results in its article. Dependencies are pinned to what was
> tested at publication time and are not actively maintained.

## Posts

| Date | Article | Folder | Download |
|---|---|---|---|
| 2026-11 | PDF parsing, from glyphs to knowledge *(article link TBD)* | [`2026-11-pdf-parsing/`](2026-11-pdf-parsing/) | [ZIP](https://github.com/basillicus/blog-companions/releases/tag/2026-11-pdf-parsing/v1) |

## Downloading a single post

You do not need to clone the entire repository to get one article's code.

- **ZIP archive (easiest):** Open [Releases](https://github.com/basillicus/blog-companions/releases) and download the
  `.zip` attached to the post's release (e.g. `2026-11-pdf-parsing.zip`).
- **Git sparse checkout (developers):**

```bash
git clone --filter=blob:none --sparse https://github.com/basillicus/blog-companions.git
cd blog-companions
git sparse-checkout set 2026-11-pdf-parsing
```

Replace `2026-11-pdf-parsing` with the folder you want.

## Contributing

Colleagues adding companion code for a new blog post: see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Unless a post folder specifies otherwise in its own `LICENSE` or `NOTICE`
file, code in this repository is licensed under the Apache License 2.0 (see
[`LICENSE`](LICENSE)).
