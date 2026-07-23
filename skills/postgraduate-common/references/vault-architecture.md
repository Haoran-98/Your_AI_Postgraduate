# Vault Architecture

Each domain vault is named `Postgraduate_<EnglishDomainSlug>`.

All generated folder and file names must be English ASCII slugs. Chinese source titles may remain inside Markdown content, but generated paths must not contain Chinese characters.

Required structure:

```text
Postgraduate_<EnglishDomainSlug>/
  .obsidian/
  .raw/
  wiki/
    index.md
    hot.md
    log.md
    causal-core/
    causal-bridges/
    variables/
    mechanisms/
    interventions/
    datasets/
    papers/
    ideas/
    research-lines/
    relations/
      semantic/
    profile/
  rag/
```

Do not create `Postgraduate_Common`. Repeated causal knowledge is copied or adapted inside each domain vault.

One domain postgraduate may own multiple research lines. Register each line under `wiki/research-lines/`, keep its idea-specific evidence separately traceable, and share only genuinely reusable domain knowledge and infrastructure.

Do not nest research lines. The maximum hierarchy depth is the postgraduate vault plus one research-line layer.
