---
title: Bazinga
hide:
  - navigation
  - toc
---

![Bazinga: numbered dots joined by a pencil become the Vulcan-salute hand and the Bazinga logo.](assets/brand/banner-light.gif#only-light)
![Bazinga: numbered dots joined by a pencil become the Vulcan-salute hand and the Bazinga logo.](assets/brand/banner-dark.gif#only-dark)

<div class="home-hero" markdown>

# Your work, your writing, your website.

<p class="home-hero__sub">A portfolio, a CV and a blog in one site you own: your photo and story, every project, a
proper CV, and posts with real equations and figures your readers can move.</p>

<p class="home-hero__actions"><a class="md-button md-button--primary" href="getting-started/">Get started</a>
<a class="md-button" href="home-and-cv/">Make it your portfolio</a>
<a class="md-button" href="writing/">Start writing</a></p>

</div>

You need Python 3.11 or newer. There is no Node and no bundler.

## Try it

Three commands, and the example site is running on your computer:

```bash
git clone https://github.com/shreejalt/Bazinga.git my-site && cd my-site
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m bazinga serve
```

Open <http://127.0.0.1:8000>. You see the example site, and it rebuilds every time you save a file.
[Getting started](getting-started.md) walks through it slowly.

## What you get

<div class="grid cards home-cards">
<ul>
<li>
<p class="card-title"><strong>Your portfolio and CV</strong></p>
::clip portfolio-tour
<p>Your photo, who you are, experience, education, projects, a CV page and a contact section, all from one settings file. <a href="home-and-cv/">Your portfolio →</a></p>
</li>
<li>
<p class="card-title"><strong>Figures your readers can move</strong></p>
::clip figure-slider
<p>A figure is a small file with sliders. It is drawn when the site is built and redrawn in the reader's browser. <a href="figures/">Interactive figures →</a></p>
</li>
<li>
<p class="card-title"><strong>A writing window with a live preview</strong></p>
::clip editor-write
<p>Click <b>Write</b> on any page. Type on the left, and the real page follows on the right. <a href="editor/">The Editor →</a></p>
</li>
<li>
<p class="card-title"><strong>Figures without code</strong></p>
::clip editor-figure-form
<p>Pick a kind of figure, type a formula as you would on paper, and the preview redraws as you type. <a href="figures/#make-one-with-the-form-no-code">The figure form →</a></p>
</li>
<li>
<p class="card-title"><strong>A map of everything you wrote</strong></p>
::clip explore-map
<p>Every page sits on one map, below what it builds on. Point at one to see what is nearest and what to read next. <a href="map-and-topics/">The map and topics →</a></p>
</li>
<li>
<p class="card-title"><strong>Ask: answers from your own pages</strong></p>
::clip ask
<p>Readers ask a question and get an answer put together from your pages, with links to the sections it used. <a href="ask-and-wiki/">Ask and the wiki →</a></p>
</li>
<li>
<p class="card-title"><strong>3-D figures you can turn</strong></p>
::clip figure-3d
<p>Surfaces, vectors, planes and cameras. Readers drag to turn the scene and drag its points. <a href="figures-3d/">3-D figures →</a></p>
</li>
</ul>
</div>

## Where to start

<div class="grid cards home-start">
<ul>
<li><strong>New here?</strong> Install it and look around: <a href="getting-started/">Getting started</a>.</li>
<li><strong>Ready to write?</strong> Follow the nine steps of <a href="writing/">Writing</a>, from your first post to publishing.</li>
<li><strong>Making it yours?</strong> Your <a href="home-and-cv/">home page and CV</a>, then the <a href="theme/">theme</a>.</li>
<li><strong>Going live?</strong> <a href="deploying/">Deploying</a> covers Vercel, Netlify, GitHub Pages and any static host.</li>
<li><strong>Looking something up?</strong> Every <a href="reference/commands/">command</a> and every <a href="reference/configuration/">setting</a>.</li>
<li><strong>Stuck?</strong> <a href="troubleshooting/">Troubleshooting and FAQ</a>.</li>
</ul>
</div>

## What's next

Start with [Getting started](getting-started.md): install Bazinga, build the example site and take a tour of its
folders.
