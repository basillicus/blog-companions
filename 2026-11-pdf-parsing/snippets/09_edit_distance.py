"""Edit distance, the basis of most text metrics (article section 9).

    uv run 09_edit_distance.py
    uv run 09_edit_distance.py ../demo/ground-truth/demo-page.md ../demo/outputs/pypdf/demo-page.md
"""

import sys

from rapidfuzz.distance import Indel, Levenshtein

print("Levenshtein('214', '21.4') =", Levenshtein.distance("214", "21.4"))
print("Indel('214', '21.4')       =", Indel.distance("214", "21.4"))
print(f"normalised similarity     = {Indel.normalized_similarity('214', '21.4'):.2f}")

if len(sys.argv) == 3:
    truth, output = (open(p).read() for p in sys.argv[1:])
    # pdf-eval normalises the Markdown (whitespace, table syntax) first, so its NID differs slightly
    print(f"raw page similarity       = {Indel.normalized_similarity(truth, output):.2f}")
