# Parsing pages with a vision-language model

The article shows the minimal call: one page image, one prompt, one
response. This guide covers what that call leaves out. The script
[`snippets/08_vlm_page.py`](../snippets/08_vlm_page.py) implements it.

## 1. Get an endpoint

Every option below speaks the OpenAI chat-completions API, so the same
client code works with all of them; only `base_url`, `api_key` and the
model name change.

| Option | Start it | `base_url` |
|---|---|---|
| llama.cpp server | `llama-server -m model.gguf --mmproj mmproj.gguf --port 8080` | `http://127.0.0.1:8080/v1` |
| vLLM | `vllm serve <hf-model-id> --port 8000` | `http://127.0.0.1:8000/v1` |
| Ollama | `ollama pull <model>` (the server runs in the background) | `http://127.0.0.1:11434/v1` |
| LM Studio | load a vision model, start the server | `http://127.0.0.1:1234/v1` |
| A hosted API | create an API key | the provider's URL |

For llama.cpp, a vision model needs its projector file (`--mmproj`) next to
the language weights; without it the server accepts the request and
silently ignores the image. Check the server's documentation for the
current flags; they change between releases.

Set `OPENAI_BASE_URL` and `OPENAI_API_KEY` once, and the scripts pick them
up. Local servers usually accept any key.

Sending pages to a hosted API sends your documents to the provider. For
confidential files, run the model locally.

## 2. Choose a model

Two kinds of model can do the job, and they are used differently.

**General VLMs** (the large chat models that accept images: Gemma, Qwen-VL,
GPT, Gemini, Claude and similar) follow a plain-language prompt such as the
one in the article. They are robust on unusual pages and good at reading
numbers in context, and slow and expensive per page. Prefer the largest
model your hardware runs at an acceptable speed; on the demo scan a 31B
model and a mixture-of-experts model both produced a perfect page.

**Document-specialised models** (granite-docling, SmolDocling, olmOCR,
MinerU's VLM, PaddleOCR-VL and others) are small and fast, but were trained
with a specific prompt and output format, for example DocTags for
granite-docling. Asked with a generic prompt through a chat API they often
do much worse than their benchmarks. Run them through the pipeline they
were built for (Docling, olmOCR's or MinerU's own tooling), as
[`snippets/07_docling_vlm.py`](../snippets/07_docling_vlm.py) does for
granite-docling.

Whatever you pick, test it on your own pages (article section 9) before
you trust it: a model that is perfect on one page can drop a heading or
loop on the next.

## 3. Prepare the page image

- **Resolution.** Render PDF pages at 150 to 200 dpi. Below about 100 dpi,
  decimal points and small digits blur; much above 200 dpi the server
  downsizes the image anyway, and you pay for the upload.
- **Size limit.** Models cut images into patches and have a budget of
  image tokens. A very large image is shrunk to fit the budget, or tiled
  into many tokens, depending on the model. The script downsizes the long
  side to 2048 pixels by default (`--max-side`).
- **One page per request.** Several pages in one image, or several images
  in one request, make the model mix them up and make the output harder to
  trace back to a page.
- **Format.** PNG for born-digital pages, so thin strokes stay sharp; the
  JPEG of a scan can be sent as it is.

## 4. Write the prompt

The article's prompt is a good default:

> Convert this page to Markdown. Use # for headings, a Markdown table for
> tables, and keep the reading order. Output only the Markdown.

Useful additions, depending on the documents:

- *"Use HTML tables (`<table>`) for tables with merged cells."* Markdown
  tables cannot express spanning cells.
- *"Write [illegible] for text you cannot read. Do not guess."* This makes
  gaps visible, though no prompt guarantees the model will not guess.
- *"Leave out running headers, footers and page numbers."* or the opposite.
  Decide, and keep it consistent with your answer key.
- *"Describe figures in one sentence in square brackets."* if figures carry
  information you need.

Pass the prompt with `--prompt`. Keep it the same across a whole
evaluation; small wording changes move the results.

## 5. Set the parameters

- **`temperature=0`.** Parsing is transcription, not writing; any
  randomness is noise.
- **`max_tokens` large enough.** A dense page with a table can need 2,000
  to 4,000 tokens. If the limit is too small, the output just stops, and
  the response's `finish_reason` is `"length"`. The script warns when that
  happens. Some servers default to a low limit when none is given.
- **Timeouts.** A large model on a local GPU can take minutes per page.
  Raise the client timeout rather than retrying, which starts the page
  again.
- **Repetition.** Generative models can get stuck repeating a line until
  they hit `max_tokens`. A mild repetition or frequency penalty (if the
  server supports one) reduces it, at the risk of penalising tables, which
  legitimately repeat. Detect it instead: the script warns when a line
  appears three or more times.

## 6. Check the output

A VLM's mistakes read fluently, so check every page automatically:

- **Finish reason.** `"length"` means the page is incomplete.
- **Repeated lines.** A sign of a loop; the rest of the page is usually
  missing.
- **Length.** If the PDF has a text layer, compare the number of words with
  the VLM output. Much shorter means dropped content; much longer means
  invented or repeated content.
- **Numbers.** For pages with a text layer, every number in the VLM output
  should appear in the text layer. For scans, compare with an OCR engine's
  numbers: disagreements are where errors are.
- **Empty table cells.** Can be correct (a blot, a dash in the original)
  or a dropped value; worth a look.

## 7. Multi-page documents

Send each page separately and join the results, as the script does; it
marks each page with `<!-- page N -->` so that every passage can be traced
back. Tables that continue across pages come out as two tables; join them
afterwards if the header repeats or the columns match. Running headers then
appear once per page and are best removed after joining.

## 8. Structured output

[`snippets/10_extract.py`](../snippets/10_extract.py) asks for JSON that
follows a schema, with `response_format={"type": "json_schema", ...}`.
Support varies:

- **vLLM, llama.cpp's server, OpenAI** and most hosted APIs enforce the
  schema while generating (constrained decoding).
- **Ollama** takes the schema in its own `format` field on its native API;
  its OpenAI-compatible endpoint supports `response_format` in recent
  versions.
- **Servers without schema support** may ignore the field. Then ask for
  JSON in the prompt, validate the result with Pydantic, and retry once on
  failure.

Constrained decoding guarantees the shape of the output, not that it ends:
some models get stuck emitting whitespace or repeating a field inside the
JSON until they hit the token limit. On the demo page, a mixture-of-experts
Gemma model did exactly that, while the dense 31B model of the same family
returned a correct record. Always set `max_tokens` and treat
`finish_reason == "length"` as a failure, as the script does; if it
happens, try another model before tuning the prompt.

Validation only checks the shape. Always run a grounding check as well:
every extracted value should appear in the source text.

## 9. Cost

Rough orders of magnitude, so you can plan: rules take milliseconds per
page on a CPU; layout and table models about a second on a GPU; a small
document VLM several seconds; a large general VLM tens of seconds to
minutes, locally or as a paid API call. For thousands of pages, consider
routing: a fast parser for every page, and the VLM only for pages where
the fast parser's output fails a check.
