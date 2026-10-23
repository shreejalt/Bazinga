---
title: "Gradient Descent, One Step at a Time"
date: 2026-10-12
summary: "Training a model means walking downhill on a loss surface. One update rule does the walking, and one number, the learning rate, decides whether the walk crawls, converges or flies off. A two-dimensional bowl shows all three."
description: "Gradient descent on a simple bowl: the update rule, why the steepest direction limits the learning rate, and what too small and too big look like."
topics: [optimization, training, visualization]
series: {name: "Learning, Visually", part: 1}
cites: [Kingma14]
---

Almost every model I train learns the same way: it measures how wrong it is, works out which direction makes it
less wrong, and takes a small step that way. That is gradient descent. In this first part of the series I want to
make it something you can see, because once you have watched it fail you understand the knob that controls it.

## A loss is a landscape

A model has parameters $\theta$, and a loss $\mathcal{L}(\theta)$ that is large when the model is wrong. If there are
two parameters, the loss is a surface over a plane: hills where the model is bad, a valley where it is good. Training
is the search for the bottom of that valley.

The gradient $\nabla \mathcal{L}(\theta)$ points uphill, in the direction where the loss grows fastest. So we step
the other way:

$$
\theta_{t+1} = \theta_t - \eta \, \nabla \mathcal{L}(\theta_t)
$$ {#eq:update}

The learning rate $\eta$ scales the step. That is the whole algorithm. Everything interesting is in what $\eta$ does.

## The smallest interesting landscape

The figure below uses a bowl that is stretched in one direction:

$$
\mathcal{L}(x, y) = \tfrac{1}{2} x^2 + \tfrac{5}{2} y^2
$$ {#eq:bowl}

Its gradient is $(x, 5y)$: the walls are five times steeper along $y$ than along $x$. Put that gradient into
[eq:update] and the two coordinates separate completely:

$$
\begin{aligned}
x_{t+1} &= (1 - \eta)\, x_t \\
y_{t+1} &= (1 - 5\eta)\, y_t
\end{aligned}
$$ {#eq:factors}

Each step multiplies $x$ by one fixed number and $y$ by another. If both numbers are smaller than 1 in size, the
path shrinks towards the minimum. If either is larger than 1 in size, that coordinate grows without end.

::figure gradient_descent

The path starts at $(-4, 1.6)$, where the loss is 14.4. At the default learning rate of 0.15, $y$ shrinks by a
factor of $|1 - 5 \times 0.15| = 0.25$ per step and $x$ by 0.85, so the path drops quickly onto the long axis of the
bowl and then slides along it. After 12 steps the loss is 0.162.

## Too small, too big, and the edge

Try the presets.

**Too small** ($\eta = 0.03$). Nothing goes wrong, it is just slow. The $x$ factor is 0.97, so after 40 steps the
loss is still 0.7. In a real model this looks like a training curve that keeps creeping down long after your
patience has run out.

**Zig-zag** ($\eta = 0.36$). Now the $y$ factor is $1 - 1.8 = -0.8$. It is negative, so $y$ changes sign on every
step: the path bounces from wall to wall. Its size still shrinks by 0.8 each time, so the walk converges, and after
20 steps the loss is below 0.001.

**Diverges** ($\eta = 0.42$). The $y$ factor is $-1.1$. Every step overshoots by more than the last, and after 30
steps the loss has grown from 14.4 to about 1950. The right panel shows it on a log scale: after a dip in the first two steps, while $x$ is still shrinking, a
straight line going up.

The edge between the last two is exactly where $|1 - 5\eta| = 1$, that is $\eta = 0.4$. Slide the learning rate
across 0.4 and watch the readout cross 1.

> [!KEY] The steepest direction sets the limit
> On a quadratic bowl, gradient descent converges only when $\eta$ is smaller than $2 / \lambda_{\max}$, where
> $\lambda_{\max}$ is the largest curvature. Here that is $2 / 5 = 0.4$. The flat directions do not get a vote.

## The best single step size

So a large step is limited by the steep direction, and a small step is slow in the flat direction. The best you can
do with one learning rate is to balance them, so that both factors in [eq:factors] have the same size:

$$
1 - \eta = 5\eta - 1 \quad\Rightarrow\quad \eta = \tfrac{1}{3}
$$

Both coordinates then shrink by $2/3$ per step. More generally, with curvatures $a < b$ the best step is
$2 / (a + b)$ and the shrink factor is $(b - a) / (b + a)$. The more stretched the bowl, the closer that factor gets
to 1, and the slower the descent, however carefully you choose $\eta$.

> [!NOTE]
> This is why optimisers such as Adam [@Kingma14] scale the step separately for each parameter. If the steep and
> flat directions get different step sizes, the stretch matters much less. [[read:writing-math]] writes out Adam's
> update rules as an example of aligned equations.

## What changes in a real model

A real loss has millions of directions instead of two, and its curvature changes from place to place. Two things
carry over unchanged. The learning rate is still capped by the sharpest direction, which is why a loss that suddenly
shoots up often means "lower $\eta$". And a learning rate that is safe is not automatically fast, which is why
training recipes warm up, decay and adapt it.

Real training also replaces the exact gradient with an average over a small batch of examples, the stochastic
version. The noise adds some jitter to the path but not a new idea.

In [[read:softmax-and-temperature|the next part]] the loss gets a concrete shape: the cross-entropy of a softmax,
the function that turns a model's raw scores into probabilities.
