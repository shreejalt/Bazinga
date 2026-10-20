---
title: "Notes on Attention (draft)"
date: 2026-10-21
status: draft
summary: "A draft that shows how unpublished work stays private: it appears in the Studio and in --drafts previews, never on the public site, in the sitemap, the feed or the search data."
topics: [attention, transformers]
builds_on: [post:welcome]
cites: [Vaswani17]
---

This post is a **draft** (`status: draft` in its front matter). A normal build skips it entirely; so does any page
whose `date` is still in the future, which is how you schedule a post.

## Scaled dot-product attention

Each query is compared with every key, and the scores weight the values [@Vaswani17]:

$$
\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V
$$ {#eq:attention}

Dividing by $\sqrt{d_k}$ in [eq:attention] acts like the temperature in [[post:welcome|the welcome post]].

> [!NOTE]
> To publish it, set `status: published` (or remove the line), or use Publish in the Studio.
