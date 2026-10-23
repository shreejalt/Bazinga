# 8. Checking

On this page you run the checks that find every problem in your posts before readers can: a misspelt topic, a link
to a page that does not exist, a formula with a missing brace. Each problem comes with its file, its line and a fix.

## Step 1: check the whole site

```bash
python -m bazinga check
```

**What you should see** when everything is fine:

```text

Checked 16 page(s): 0 error(s), 0 warning(s).
```

The command checks every page in `content/` (posts, papers and projects), drafts included. It ends with exit code 0
when there are no errors and 1 when there is at least one, so you can use it in scripts. A page whose header cannot
be read at all counts as an error too.

## Step 2: read a problem and fix it

Here is a draft with six mistakes on purpose:

```markdown
---
title: "Broken on purpose"
date: 2026-10-22
status: draft
summary: "Mistakes for the checks."
topics: [attenton]
builds_on: [read:welcom]
---

See [[read:writing-maths]] and [@Vaswani]. The value $\frac{a}{b$ is wrong.

::figure softmax_temperature | start: Sharpest
```

**What you should see:**

```text
content/reads/broken.md:6: error: unknown topic 'attenton'
    hint: did you mean attention?
content/reads/broken.md:7: error: builds_on: read:welcom is not a page of this site
    hint: did you mean read:welcome?
content/reads/broken.md:10: error: [@Vaswani] is not in content/references.yml
    hint: did you mean Vaswani17?
content/reads/broken.md:10: error: [[read:writing-maths]] is not a page of this site
    hint: did you mean read:writing-math?
content/reads/broken.md:10:63: error: maths: this { is never closed.
    hint: add the matching } where the group ends
content/reads/broken.md:12: error: figure 'softmax_temperature': figure 'softmax_temperature' has no preset 'Sharpest' (presets: 'Sharp', 'Flat'). Did you mean 'Sharp'?
    hint: fix the figure file, or run: python -m bazinga figure test softmax_temperature

Checked 17 page(s): 6 error(s), 0 warning(s).
```

Each problem starts with the file and the line (and, for maths, the column), says what is wrong, and gives a hint
on the next line. Fix them from the top; one fix often clears several messages.

## Check one page, or only errors

Give one or more files to check just those:

```bash
python -m bazinga check content/reads/my-first-post.md
```

**What you should see:**

```text
Checked 1 page(s): 0 error(s), 0 warning(s).
```

Add `--errors-only` to hide warnings:

```bash
python -m bazinga check --errors-only
```

## Errors and warnings

**Errors** would make a wrong page, so they stop `python -m bazinga build`, the same build your host runs. **Warnings** are worth a look but do not stop
anything.

| Errors (the build stops) | Warnings (the build goes on) |
|---|---|
| a maths mistake | a long equation row that will scroll on phones |
| an unknown topic, citation key, page id or figure | a heading that skips a level, or a `#` heading in the body |
| an unknown figure preset | an image without alt text, or a link without text |
| a published page without a date, summary or topics | a draft without a summary or topics |
| a description over 155 characters, or more than four topics | a summary over 320 characters |
| a published page that links to, or builds on, a draft | a Markdown link that matches no page of the site |
| a missing image | an unknown callout type, such as `[!NOTES]` |
| a page without a title | an unknown figure option, or an unknown code language |
| an `explains:` key that is not in `references.yml`, or a drawing that fails | a code block that is never closed |
| a series `part` below 1 | an `updated:` date before the `date:` |

These are the common ones. [Troubleshooting](../troubleshooting.md) has more messages and what to do about them.

A draft gets the same checks, except that a missing summary or topics is only a warning until you publish it.

## What the build does with problems

`python -m bazinga build` builds only published pages, so a draft never stops it. When a published page has an
error, the build writes nothing and lists the problems:

```text
6 problem(s) stop the build:
content/reads/broken.md:6: error: unknown topic 'attenton'
    hint: did you mean attention?
…

Nothing was written. Fix the problems above (each has a hint) and build again.
```

Your last good `_site/` stays as it was. Hosts such as Vercel and Netlify run the same build, so a page with an error
never goes live; the old site stays up.

When the build succeeds but finds warnings, it says so on its last line:

```text
Built 14 pages (36 HTML files) into _site/ in 1.00s; 1 warning(s), see: python -m bazinga check
```

## In your browser and in the Editor

- With `python -m bazinga serve --drafts`, a page with problems shows a box at the top: **6 things to fix before
  publishing**, with each problem and its line.
- The Editor's **Checks** drawer lists the same problems as you type. Clicking one jumps to its line. See
  [The Editor](../editor.md).

## Test your figures too

The checks make sure a figure exists. To make sure it also works at every setting, run its test:

```bash
python -m bazinga figure test softmax_temperature
```

```text
ok   softmax_temperature  (34 ms for all states)
```

Leave out the name to test every figure. See [Interactive figures](../figures.md).

## What's next

Your post has no problems left. Now put it on the live site: [9. Publishing](publishing.md).
