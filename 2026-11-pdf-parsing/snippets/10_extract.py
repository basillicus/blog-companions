"""From a parser's Markdown to records that follow a schema, then a grounding
check (article section 11).

    uv run 10_extract.py ../demo/outputs/docling/demo-page.md --model gemma4-31b

The server must support response_format json_schema (vLLM, llama.cpp's
server, OpenAI and most hosted APIs do); see ../docs/vlm.md.
"""

import argparse
import os

from openai import OpenAI
from pydantic import BaseModel, Field


class StationMean(BaseModel):
    station: str = Field(description="Station letter, e.g. 'A'")
    location: str
    temperature_c: float
    visibility_m: float
    phosphorus_ug_per_l: float


class Report(BaseModel):
    lake: str
    year: int
    stations: list[StationMean]
    bathing_limit_exceeded: bool


def ungrounded(report: Report, source: str) -> list[str]:
    """Extracted values that do not appear in the source text."""
    values = [report.lake, str(report.year)]
    for s in report.stations:
        values += [s.location, f"{s.temperature_c:g}", f"{s.visibility_m:g}",
                   f"{s.phosphorus_ug_per_l:g}"]
    return [v for v in values if v not in source]


ap = argparse.ArgumentParser()
ap.add_argument("markdown")
ap.add_argument("--model", required=True)
ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8080/v1"))
args = ap.parse_args()

markdown = open(args.markdown).read()
client = OpenAI(base_url=args.base_url, api_key=os.environ.get("OPENAI_API_KEY", "none"))
response = client.chat.completions.create(
    model=args.model,
    temperature=0,
    max_tokens=4096,
    messages=[
        {"role": "system", "content": "Extract the requested fields from the "
            "document. Use only values that appear in it."},
        {"role": "user", "content": markdown},
    ],
    response_format={"type": "json_schema", "json_schema": {
        "name": "report", "schema": Report.model_json_schema()}},
)
if response.choices[0].finish_reason == "length":
    raise SystemExit("output cut off at max_tokens: the model may be looping inside the JSON")
report = Report.model_validate_json(response.choices[0].message.content)
print(report.model_dump_json(indent=2))
print("not found in the source:", ungrounded(report, markdown))
