# Models

## Target

**Qwen3.8-27B**, quantized Q4_K_M (~16 GB on disk).

Used identically on all three backends, served from the same GGUF file, to
make the comparisons direct. On Ollama it is exposed as
`qwen3.8:27b-mtp-q4_K_M`.

## Drafter (speculative decoding)

**Qwen3.8-27B-DFlash2**, quantized Q8_0.

For Lucebox the drafter requires a repack into a format different from the one
used by llama.cpp — the conversion script is in the sibling Lucebox
reproduction repository, not here.

## Other models present on the machine

Not used for the published measurements, listed for completeness:
`ornith-1.5:9b` and `:35b`, `muse-glimmer:30b`, `hauhau-a3b:35b` (32k and
256k), `qwen3.5:0.8b`, `qwen2.5:0.5b` and `:1.5b`, `nomic-embed-text`.

## Note on identification

The GGUF files are referenced by path and blob hash in the raw JSON files in
`raw/`. The target model is the same blob in all the measurements, verifiable
from the `model` field of each file.
