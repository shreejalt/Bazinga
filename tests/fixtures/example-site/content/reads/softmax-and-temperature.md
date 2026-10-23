---
title: "Softmax, Temperature and Entropy"
date: 2026-10-14
summary: "A model's last layer gives raw scores; the softmax turns them into probabilities. Dividing the scores by a temperature makes those probabilities sharper or flatter, and entropy measures how spread out they are. One figure shows all three moving together."
description: "How the softmax turns scores into probabilities, what a temperature does to them, and how entropy measures the spread, with a figure to play with."
topics: [probability, information-theory, neural-networks]
series: {name: "Learning, Visually", part: 2}
builds_on: [read:gradient-descent]
cites: [Hinton15]
---

In [[read:gradient-descent|the first part]] the loss was a made-up bowl. In a classifier the loss has a specific
shape, and it starts with one small function: the softmax. I use it every day without thinking, so this part is
my attempt to think about it properly.

## From scores to probabilities

The last layer of a classifier produces one number per class, a score or *logit* $z_i$. Scores can be any real
number, negative included, and they do not add up to anything in particular. To read them as probabilities we
need two things: every value positive, and all of them summing to 1. The softmax does both:

$$
p_i = \frac{e^{z_i}}{\sum_{j=1}^{K} e^{z_j}}
$$ {#eq:softmax}

The exponential makes every score positive, and dividing by the sum makes them add up to 1. The exponential also
exaggerates gaps: a score one point higher gets $e \approx 2.7$ times the weight.

One property is worth knowing by heart. Adding the same constant $c$ to every score changes nothing, because
$e^{z_i + c} = e^c e^{z_i}$ and the $e^c$ cancels above and below. Only the *differences* between scores matter.
That is why careful code subtracts the largest score before exponentiating, as the code sample in
[[read:welcome]] does: the result is the same, and nothing overflows.

## Temperature

Now divide every score by a number $T$ before the softmax:

$$
p_i(T) = \frac{e^{z_i / T}}{\sum_{j} e^{z_j / T}}
$$ {#eq:temperature}

Dividing by $T$ scales every *difference* between scores by $1/T$. A small $T$ stretches the gaps, so the top class
takes nearly everything. A large $T$ squeezes them, so the classes look alike. At the two ends, $T \to 0$ gives all
the probability to the largest score (the hard arg max), and $T \to \infty$ gives the uniform $1/K$ to every class.

::figure softmax_temperature

The figure has five classes with scores 3.0, 2.2, 1.6, 1.1 and 0.4. At $T = 1$ the top class, "cat", gets 52%. At
$T = 0.2$ it gets 98%; at $T = 4$ only 27%, close to the uniform 20%. The right panel traces the top class's share
over the whole range of temperatures, falling from almost 1 towards $1/K$.

Distillation uses exactly this knob: a large model's probabilities are softened with a high temperature, so a
small model can learn from how the wrong classes compare, not just which class won [@Hinton15, sec. 2].

## Entropy: one number for the spread

To talk about "sharp" and "flat" precisely I use the entropy of the distribution:

$$
H(p) = -\sum_{i=1}^{K} p_i \log p_i
$$ {#eq:entropy}

With the natural logarithm it is measured in *nats*. It is 0 when one class has all the probability, and it is
largest, $\log K$, when every class has $1/K$. For five classes that maximum is $\log 5 \approx 1.61$ nats.

The readouts under the figure show it. At $T = 0.2$ the entropy is 0.10 nats; at $T = 1$ it is 1.27; at $T = 4$
it is 1.58, nearly the maximum. Switch to 8 classes and the ceiling rises to $\log 8 \approx 2.08$.

> [!TIP]
> One way I read entropy: $e^{H}$ is the number of equally likely classes that would be just as uncertain. At
> $T = 1$, $e^{1.27} \approx 3.6$, so the five scores behave like a fair choice among three or four classes.

## How the softmax learns

To train a classifier we compare $p$ with the right answer $y$ (a one-hot vector) using the cross-entropy
$\mathcal{L} = -\sum_i y_i \log p_i$, which is just $-\log p$ of the correct class. Its gradient with respect to the
scores comes out remarkably clean:

$$
\frac{\partial \mathcal{L}}{\partial z_i} = p_i - y_i
$$ {#eq:ce-gradient}

Each score is pushed by "how much probability it got, minus how much it should have got". This is the gradient that
the update rule of the first part follows downhill.

There is a catch hidden in the softmax itself. How much $p_i$ moves when a score $z_j$ moves is

$$
\frac{\partial p_i}{\partial z_j} = p_i \, (\delta_{ij} - p_j)
$$ {#eq:jacobian}

where $\delta_{ij}$ is 1 when $i = j$ and 0 otherwise. When the softmax is very sharp, one $p_i$ is close to 1 and
the rest are close to 0, and every entry of [eq:jacobian] is close to 0. A saturated softmax barely responds to its
inputs, so gradients flowing back through it are tiny.

> [!KEY] Temperature controls two things at once
> How confident the probabilities look, measured by the entropy, and how much gradient can flow back through the
> softmax. Very sharp means confident and hard to train through.

That catch is the reason for a small division you have probably seen in a famous formula. In
[[read:attention-from-scratch|the next part]] the softmax runs over words instead of classes, and its temperature
is fixed at $\sqrt{d}$.
