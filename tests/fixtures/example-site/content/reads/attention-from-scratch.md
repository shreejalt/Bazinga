---
title: "Attention from Scratch"
date: 2026-10-16
summary: "Scaled dot-product attention is a softmax over similarities: each word scores every other word, turns the scores into weights and mixes what it finds. This part builds it from the pieces of the first two, and shows why the scores are divided by the square root of d."
description: "Scaled dot-product attention built from a dot product and a softmax, and why the scores are divided by √d, with a heatmap you can change."
topics: [attention, transformers, linear-algebra]
series: {name: "Learning, Visually", part: 3}
builds_on: [read:softmax-and-temperature]
cites: [Vaswani17]
---

Attention sounds grander than it is. Once you have [[read:softmax-and-temperature|the softmax]], you need one more
ingredient, the dot product, and one small correction that this part is mostly about.

## Three roles for every word

Start with a sentence of $n$ words, each already turned into a vector. Attention gives every word three versions
of itself, each made by multiplying its vector by a learned matrix:

- a **query** $q_i$: what this word is looking for;
- a **key** $k_j$: what this word offers to others who are looking;
- a **value** $v_j$: what this word hands over when it is chosen.

Queries and keys have the same length $d$, so they can be compared with a dot product. A large $q_i \cdot k_j$
means word $j$ matches what word $i$ is looking for.

## The recipe

For one word $i$, attention does three things. Score every word $j$, turn the scores into weights with a softmax,
and take the weighted average of the values:

$$
\begin{aligned}
s_{ij} &= \frac{q_i \cdot k_j}{\sqrt{d}} \\
a_{ij} &= \frac{e^{s_{ij}}}{\sum_{m=1}^{n} e^{s_{im}}} \\
o_i &= \sum_{j=1}^{n} a_{ij} \, v_j
\end{aligned}
$$ {#eq:attention-rows}

The weights $a_{ij}$ in each row are positive and sum to 1, so the output $o_i$ is a blend of the values, mostly of
the words that matched best. Stacking the queries, keys and values as the rows of matrices $Q$, $K$ and $V$ does
every word at once, and gives the formula from the paper that introduced the Transformer [@Vaswani17, sec. 3.2.1]:

$$
\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V
$$ {#eq:attention}

There $d_k$ is the length of a key, the $d$ above. Here is the same thing as a picture:

::drawing learning.attention | Queries and keys make the scores; scaled and softmaxed, they decide how much of each value goes into the output.

## Why divide by √d?

Compare the first line of [eq:attention-rows] with the temperature from the last part: dividing the scores by
$\sqrt{d}$ before a softmax *is* a temperature, $T = \sqrt{d}$. Why that value?

The paper's reasoning fits in a footnote [@Vaswani17, sec. 3.2.1]. Suppose the entries of $q$ and $k$ are independent, with
mean 0 and variance 1. Then each product $q_m k_m$ has mean 0 and variance 1, and the dot product adds $d$ of them:

$$
\operatorname{Var}(q \cdot k) = \sum_{m=1}^{d} \operatorname{Var}(q_m k_m) = \sum_{m=1}^{d} 1 = d
$$ {#eq:variance}

So the scores spread out like $\sqrt{d}$, their standard deviation. With long vectors the gaps between scores get
large, the softmax becomes nearly one-hot, and, as the Jacobian in the last part showed, a nearly one-hot softmax
passes back almost no gradient. The paper puts it as the dot products growing large and "pushing the softmax function
into regions where it has extremely small gradients". Dividing by $\sqrt{d}$ brings the spread back to about 1,
whatever $d$ is.

## See it on five words

The figure takes the five words "the cat chased a mouse". Their queries and keys are random numbers with mean 0 and
variance 1, which is exactly the situation the argument assumes, and is roughly where a model starts before it has
learned anything. Each row is one word's attention over all five.

::figure attention_weights

At the defaults, $d = 64$ and the scores are divided by $\sqrt{64} = 8$. Their spread is 1.1, the weights are mixed
(the largest weight in a row is 0.49 on average) and the average entropy is 1.27 nats, of at most
$\log 5 \approx 1.61$.

Now press **Not divided**. The same scores, raw, have a spread of 9.0, close to the predicted $\sqrt{64} = 8$.
Almost every row puts nearly all its weight on one word: the largest weight averages 0.95 and the entropy drops to
0.17. Nothing about the words changed; only the temperature did.

Step through the vector sizes with the scores not divided, and the spread grows: 1.5 at $d = 4$, 3.9 at $d = 16$,
9.0 at $d = 64$. Divided by $\sqrt{d}$, it stays between 0.8 and 1.1. The temperature slider sits on top of the
division, so you can still sharpen or soften the weights by hand.

> [!KEY] The one thing to remember
> The $\sqrt{d}$ is not a magic constant. It is the temperature that keeps the spread of the scores near 1 when the
> entries of queries and keys have variance 1, so the softmax stays in the range where it can learn.

The size it matters at is real: in the paper's base model, each attention head uses $d_k = 64$
[@Vaswani17, sec. 3.2.2], so every score is divided by 8. The paper also notes that for small $d_k$ the plain dot
product and an older, additive form of attention perform similarly, and that without the scaling the dot product
falls behind as $d_k$ grows [@Vaswani17, sec. 3.2.1].

## What attention cannot see

Look again at [eq:attention-rows]. If I shuffle the words, every score moves with its word and each output is the
same as before, just in the new order. Attention compares *contents* only; it has no idea which word came first. (The formula itself also appears in
[[read:welcome]], as the example of a labelled equation.) To
tell "the cat chased a mouse" from "a mouse chased the cat", the Transformer adds a position signal to every word
before attention runs. That signal is built from sines and cosines, and [[read:fourier-features|the last part]]
explains why that is a good idea.
