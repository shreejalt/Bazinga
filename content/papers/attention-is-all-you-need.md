---
title: "Transformer — Attention Is All You Need"
short: "Transformer"
date: 2026-10-19
summary: "The 2017 paper that dropped recurrence and convolution from sequence models and kept only attention. This explainer walks through scaled dot-product attention, multiple heads, the encoder and decoder stacks, positional encodings and the training recipe, with the numbers the paper reports."
description: "The Transformer explained: scaled dot-product attention, multi-head attention, encoder and decoder stacks, positional encodings and the training recipe."
topics: [attention, transformers, neural-networks]
explains: [Vaswani17]
builds_on: [read:attention-from-scratch]
cites: [Vaswani17, He15, Kingma14]
---

Before this paper, a model that translated a sentence read it one word at a time, carrying a hidden state from each
word to the next. The Transformer reads every word at once and lets each one look directly at all the others, with
attention as the only way information moves between positions [@Vaswani17]. This page goes through the parts in
the order the paper builds them. The attention itself is explained step by step in [[read:attention-from-scratch]];
here it is one block among several.

## Scaled dot-product attention

Every position produces a query, a key and a value. Stacking them as the rows of $Q$, $K$ and $V$, attention for
all positions at once is a single expression:

$$
\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V
$$ {#eq:attention}

Each row of $QK^\top$ scores one query against every key; the softmax turns a row of scores into weights (see
[[read:softmax-and-temperature]]), and the weights mix the values. The division by $\sqrt{d_k}$ is the paper's own
addition. If the entries of a query and a key are independent with mean 0 and variance 1, their dot product has
mean 0 and variance $d_k$, so for wide vectors the scores spread out and the softmax saturates, leaving tiny
gradients [@Vaswani17, p. 4]. Dividing by $\sqrt{d_k}$ brings the spread back to about 1. The figure starts with
the division switched off; switch it on and watch the rows soften.

::figure attention_weights | start: Not divided

## Several heads instead of one

One attention averages everything a position finds into one mix. The paper instead runs $h$ smaller attentions in
parallel, each on its own learned projection of the queries, keys and values, and concatenates the results:

$$
\begin{aligned}
\operatorname{head}_i &= \operatorname{Attention}(QW_i^Q, KW_i^K, VW_i^V) \\
\operatorname{MultiHead}(Q, K, V) &= \operatorname{Concat}(\operatorname{head}_1, \dots, \operatorname{head}_h)\, W^O
\end{aligned}
$$ {#eq:heads}

With a model width $d_{\text{model}} = 512$ and $h = 8$ heads, each head works in $d_k = d_v = 64$ dimensions, so the
total cost is close to that of one full-width attention [@Vaswani17].

::pagebreak

## The encoder and the decoder

Both halves are stacks of $N = 6$ identical layers. An encoder layer has two sub-layers: multi-head self-attention,
where every position attends to every position of the input, and a feed-forward network applied to each position
separately:

$$
\operatorname{FFN}(x) = \max(0,\, xW_1 + b_1)\, W_2 + b_2
$$ {#eq:ffn}

Its inner layer is $d_{ff} = 2048$ wide. Around each sub-layer sits a residual connection [@He15] followed by layer
normalisation, so a sub-layer's output is $\operatorname{LayerNorm}(x + \operatorname{Sublayer}(x))$.

A decoder layer adds a third sub-layer that attends over the encoder's output. Its self-attention is masked: a
position may only attend to the positions before it, so the model cannot look at the words it is about to predict.

| Setting | Base model |
|---|---:|
| Layers in each stack, $N$ | 6 |
| Model width, $d_{\text{model}}$ | 512 |
| Heads, $h$ | 8 |
| Width per head, $d_k = d_v$ | 64 |
| Feed-forward width, $d_{ff}$ | 2048 |

## Where each word is

Attention by itself does not know the order of the words: shuffle the input and every output is shuffled the same
way. The paper adds a fixed pattern of sines and cosines to each input embedding, a different frequency in each
dimension:

$$
\begin{aligned}
PE_{(pos,\, 2i)} &= \sin\left(pos / 10000^{2i/d_{\text{model}}}\right) \\
PE_{(pos,\, 2i+1)} &= \cos\left(pos / 10000^{2i/d_{\text{model}}}\right)
\end{aligned}
$$ {#eq:position}

Why sums of sines make a good ruler for positions is the subject of [[read:fourier-features]].

## How it was trained

The models were trained with Adam [@Kingma14] with $\beta_1 = 0.9$, $\beta_2 = 0.98$ and $\epsilon = 10^{-9}$, and a
learning rate that rises linearly for the first 4000 steps and then falls with the inverse square root of the step
number. Dropout of 0.1 and label smoothing of 0.1 regularise the base model [@Vaswani17].

> [!KEY]
> On WMT 2014 English-to-German translation the big Transformer reached 28.4 BLEU, more than 2 BLEU above the best
> earlier results, ensembles included [@Vaswani17].

## What came next

Everything in this paper is still inside today's language models: the scaled attention of [eq:attention], the heads
of [eq:heads], the residual stream and the feed-forward blocks. What changed most is scale, and the positional
encoding, which many later models learn or replace.
