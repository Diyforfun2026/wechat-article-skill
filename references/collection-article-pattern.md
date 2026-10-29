# Collection Articles + Code Repositories

> A pattern that shows up constantly with technical tutorial accounts: the article is a **collection**
> (合集 / 汇总 / 一文搞懂) linking to N sub-articles and usually to a GitHub repository.
>
> This file is the recommended handling pattern for it.

## Recognising the pattern

Treat an article as a collection when **any two** of these hold:

1. The title contains 合集 / 汇总 / 资源 / 系列 / 一文搞懂 / "collection"
2. The body contains a numbered link list — `##### [1. xxx](...)`, `##### [2. yyy](...)`
3. The body contains a `https://github.com/<user>/<repo>` URL
4. The body mentions 配套代码 / 代码地址 / "companion code"

## The 5-step / 3-minute flow

### Step 1 — Fetch the collection article

```bash
python3 scripts/fetch_fast.py "<collection URL>" > /tmp/summary.md
```

Fast path, ~2s. If the body comes back short, run the 4-tier chain instead:
```bash
python3 scripts/wechat_article.py "<collection URL>" > /tmp/summary.md
```

### Step 2 — Find the repository URL

```bash
grep -E "github\.com" /tmp/summary.md
```

Usually 1–3 repository URLs. Mind the `user/repo` spelling.

### Step 3 — List the repo's example directories

```bash
curl -sL "https://api.github.com/repos/<user>/<repo>/contents/examples" \
  | python3 -c "import json,sys; [print(i['name']) for i in json.load(sys.stdin) if i.get('type')=='dir']"
```

High value: this surfaces every example project, including ones the README never mentions.

**Fallbacks**: private repo → ask the user; 403 → add a GitHub token; empty → try the
`tree/main` path.

### Step 4 — Pull the README index via jsdelivr

```bash
curl -sL --max-time 15 "https://cdn.jsdelivr.net/gh/<user>/<repo>@main/README.md" > /tmp/readme.md
```

**Why jsdelivr and not raw.githubusercontent.com**: raw.githubusercontent.com is frequently blocked
on Chinese networks (15s timeout in testing). `cdn.jsdelivr.net/gh/<user>/<repo>@<branch>/<path>`
is a stable mirror. Fallback: `https://ghproxy.net/https://raw.githubusercontent.com/<user>/<repo>/main/README.md`.

### Step 5 — Decide which sub-articles to actually fetch

**Default: fetch none.** Reasons:
- The collection article *is* the tutorial outline — title + link is what the reader wants
- The README and `examples/` listing supply the index
- Sub-articles are highly redundant with each other (each one re-introduces the basics)
- Bulk-fetching WeChat articles risks rate-limiting

**Fetch sub-articles only when**:
- The user explicitly asks "what does part #7 cover?"
- A summary needs a specific detail that only one sub-article has
- There are ≤ 5 sub-articles and they are all high-value

## Summary document structure

```markdown
# <Collection name> — summary and reusable techniques

**Source**: <account> collection + GitHub repo [<repo URL>](...)
**Original**: <collection mp.weixin URL>
**Fetched**: YYYY-MM-DD
**Status**: the original is archived at `<path>`; this file is the **learning path + technique
extraction + fit assessment for our own project**

---

## 1. Hardware the author used (inferred from the code)
[chip, pin map, board]

## 2. The N examples in the repository
| directory | concept | relevance to our project |
|---|---|---|

## 3. The published articles
| # | title | link | companion code |

## 4. Recommended learning path (4 weeks)
[week by week, what to do each day]

## 5. Fit for our project
### ✅ directly reusable
### ⚠️ usable with modification
### ❌ not applicable

## 6. Key code snippets worth copying
## 7. Reference links
```

**Section 5 is the point.** The value is *"what can we use this for"*, not a transcription of the
tutorial.

## Verification checklist

- [ ] Collection original archived
- [ ] Summary written as a separate file
- [ ] Repository URL recorded (the repo is a more durable asset than the article)
- [ ] At least one example code excerpt proves you actually read the code
- [ ] Section 5 lists ≥ 3 ✅ and ≥ 1 ⚠️ and ≥ 1 ❌
- [ ] Filenames carry a `YYYY-MM-DD` suffix

## Anti-patterns

1. ❌ Loop `wechat_article.py` over all 15+ sub-articles
2. ❌ Make the summary a copy of the collection's table of contents (no added information)
3. ❌ Skip the GitHub repository (missing the most durable asset)
4. ❌ Write a summary unrelated to your own project (it becomes generic trivia, not team knowledge)
5. ❌ Fetch the README via `raw.githubusercontent.com` (frequently times out)

## Related

- [fast-path.md](fast-path.md) — fetching the collection article itself
- [pure-image-articles.md](pure-image-articles.md) — when even the collection can't be read
