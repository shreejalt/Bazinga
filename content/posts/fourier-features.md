---
title: "Sums of Sines: From Fourier Series to Positional Encodings"
date: 2026-10-18
summary: "Add enough sine waves and you can draw almost any shape, even a square wave with sharp corners. The same idea tells a Transformer where each word sits, and helps small networks learn fine detail. The last part of the series follows sines from a square wave to both."
description: "Why sums of sines can approximate functions, how Transformers use sinusoids to encode position, and how Fourier features help networks learn fine detail."
topics: [signals, transformers, neural-networks]
series: {name: "Learning, Visually", part: 4}
builds_on: [post:attention-from-scratch]
cites: [Vaswani17, Tancik20]
---

[[post:attention-from-scratch|The last part]] ended with a gap: attention compares what words *are*, not where they
*are*. The fix in the Transformer is a set of sine waves. First I want to show why sines are such a good material to
build with, using a stubborn shape: a square wave.

## A square wave out of smooth curves

A square wave jumps between $-1$ and $1$; every sine is smooth. It seems hopeless to build one from the other.
But add the right sines and the sum creeps towards the square:

$$
\operatorname{sq}(x) = \frac{4}{\pi} \left( \sin x + \frac{\sin 3x}{3} + \frac{\sin 5x}{5} + \cdots \right)
$$ {#eq:square}

Only odd frequencies appear, and the $k$-th one has weight $1/k$. Drag the slider to add terms one at a time.

::figure fourier_series

With one term the "square" is just a sine, scaled by $4/\pi$; its root-mean-square error against the square wave is
0.435. With three terms (the default) it is 0.259, and with forty it is 0.077. The flat parts flatten and the edges
steepen.

## Where the weights come from

Why $1/k$, and why only odd $k$? Sines of different whole-number frequencies are *orthogonal* on
$[-\pi, \pi]$: the integral of $\sin(jx)\sin(kx)$ over that interval is 0 unless $j = k$, when it is $\pi$. They
behave like the perpendicular axes of a coordinate system, so the weight of each one is a projection, exactly like
reading off a vector's coordinate with a dot product:

$$
b_k = \frac{1}{\pi} \int_{-\pi}^{\pi} \operatorname{sq}(x) \sin(kx) \, dx
$$ {#eq:coefficient}

For the square wave this works out to $b_k = 4 / (\pi k)$ when $k$ is odd and 0 when $k$ is even, which is
[eq:square]. Any reasonable periodic function has such a list of weights (in general for cosines as well as sines), and
the sum built from them gets as close as you like, in the root-mean-square sense, as you add terms.

> [!WARNING] The overshoot does not go away
> Next to each jump the sum overshoots. The figure's "Overshoot" readout is 13.7% of the jump with one term, 9.4%
> with three, and 9.0% from ten terms on. More terms squeeze the overshoot closer to the jump, but it never drops
> below about 9%. This is the Gibbs phenomenon, and one reason sharp edges are hard to build out of sines.

## Sines as a ruler for positions

Now the Transformer. Each position $p$ in a sentence gets a vector of the same length $d_{\text{model}}$ as the word
vectors, and it is added to the word's vector before attention runs. The entries come in sine and cosine pairs
[@Vaswani17, sec. 3.5]:

$$
\begin{aligned}
PE_{(p,\, 2i)} &= \sin\!\left(p \,/\, 10000^{2i / d_{\text{model}}}\right) \\
PE_{(p,\, 2i+1)} &= \cos\!\left(p \,/\, 10000^{2i / d_{\text{model}}}\right)
\end{aligned}
$$ {#eq:pe}

Each pair $i$ is one wave with its own frequency. The first pair turns fast and the last ones very slowly; the
wavelengths "form a geometric progression from $2\pi$ to $10000 \cdot 2\pi$". Read together, the fast pairs tell
neighbouring positions apart and the slow ones say roughly where in a long text you are, like the hands of a clock.

Why sines and not just the number $p$? The paper's reason is that it should make relative positions easy: for any
fixed offset $k$, the encoding of $p + k$ is a linear function of the encoding of $p$. For one pair with frequency
$\omega$ you can check it with the angle-addition formulas:

$$
\begin{pmatrix} \sin \omega (p + k) \\ \cos \omega (p + k) \end{pmatrix}
=
\begin{pmatrix} \cos \omega k & \sin \omega k \\ -\sin \omega k & \cos \omega k \end{pmatrix}
\begin{pmatrix} \sin \omega p \\ \cos \omega p \end{pmatrix}
$$ {#eq:shift}

Moving $k$ places is a rotation that depends on $k$ only, not on where you start. A layer that has learned "look one
word back" can apply the same matrix at every position.

> [!NOTE]
> The paper is honest that this was a hypothesis. Learned position vectors gave nearly the same result: 25.7 BLEU
> against 25.8 for the sinusoids, on its English-to-German development set [@Vaswani17, table 3]. The authors kept the
> sines because they might let the model handle sentences longer than any it saw in training.

## Sines that help networks see detail

The same trick shows up somewhere I did not expect it. Train a small network that takes a pixel's coordinates
$(x, y)$ and outputs its colour, and it learns a blurry picture: networks fed raw coordinates pick up low frequencies
easily and high frequencies hardly at all, a tendency known as spectral bias [@Tancik20].

Tancik and colleagues fix this by passing the coordinates through sines first:

$$
\gamma(\mathbf{v}) = \left[ \cos(2\pi B \mathbf{v}),\; \sin(2\pi B \mathbf{v}) \right]
$$ {#eq:fourier-features}

where each entry of the matrix $B$ is drawn at random from a normal distribution with standard deviation $\sigma$
[@Tancik20, sec. 6.1]. The network then sees a whole list of waves at many frequencies, much like the Transformer's
position vectors, and fine detail becomes learnable. The scale $\sigma$ is a knob much like the learning rate in
[[post:gradient-descent|the first part]]: too small and the result is oversmoothed, too large and it is noisy. On
their natural-image task $\sigma = 10$ worked best [@Tancik20, fig. 10].

> [!KEY] One idea, three places
> A square wave, a word's position and a pixel's coordinates all become easier to work with once they are written
> as a list of sines at different frequencies.

That closes the series. If you came here for the website rather than the maths, [[post:welcome]] shows how each of
these pages was written, and [[post:writing-math]] covers the equations.
