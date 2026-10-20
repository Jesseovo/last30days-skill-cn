<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme-cover-dark.svg" />
    <img src="assets/readme-cover-light.svg" width="880" alt="last30days-cn · A little curiosity, backed by sources. A quiet pixel desk and a curious cat." />
  </picture>
</p>

<p align="center">
  <strong>What has the Chinese internet been talking about?</strong><br />
  <sub>Last-30-days research for your AI agent. A small daily hot board for you.</sub>
</p>

<p align="center">
  <a href="https://jesseovo.github.io/last30days-skill-cn/">Open the daily hot board ↗</a> &ensp;·&ensp; <a href="#start">Hand it to your agent</a>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · <b>English</b> · <a href="docs/usage.en.md">Usage guide</a> · <a href="release-notes.md">Release notes</a>
</p>

---

<a id="start"></a>

## Hand it to your agent

Copy this sentence into the AI agent you already use:

```text
Install and configure https://github.com/Jesseovo/last30days-skill-cn, check which sources are available, and use it to show me today's cross-platform hot board.
```

Works with agents that can run shell commands, including Claude Code, Codex, Cursor and Gemini CLI. Let the agent handle installation, environment checks and the first run. It will ask you to complete any required platform login.

## Bring a question. Leave with a trail.

Research a product, follow a developing story, or see what's trending today. last30days-cn searches recent discussions, ranks them by relevance, recency and engagement, and groups the same event across platforms while keeping the original sources.

**One topic, a grounded report.** Eight Chinese platforms by default: Weibo, Xiaohongshu (RED), Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu and Toutiao. Add Hacker News, GitHub and Reddit, or connect an installed upstream skill for more overseas sources.

**One page, a view of today.** The [daily hot board](https://jesseovo.github.io/last30days-skill-cn/) brings together Chinese hot lists, tech news and Hacker News. Search a keyword, spot shared topics, or read through one source.

**Sources stay attached.** Get compact agent evidence, Markdown, JSON and offline HTML. Reports state which sources returned results, how they were retrieved, and where coverage is missing.

## A small window into today

[**Open the daily hot board ↗**](https://jesseovo.github.io/last30days-skill-cn/) · Automatically collected at **08:00 / 12:00 / 20:00 Beijing time**.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme-discovery-dark.svg" />
    <img src="assets/readme-discovery-light.svg" width="720" alt="A pixel cat's curiosity station: following little clues through the conversations of the day." />
  </picture>
</p>

Weibo, Baidu, Douyin, Toutiao, Bilibili and Zhihu bring the day's conversations. IT Home, Huxiu, SSPAI, iFanr, Solidot and Hacker News open another window. Add your own RSS feeds and make it a little more yours.

Scan the top items on desktop, or settle into one source on mobile. Keyword search, dark mode and shared topics across platforms are all close at hand.

Want your own board? Ask your agent to follow the [deployment notes](docs/usage.en.md#daily-hot-board-site) and enable scheduled publishing in your repository.

## Follow the thread a little further

The hot board is a snapshot of current rankings. Topic research looks back over a chosen date window.

> What is trending in AI today? Pick three stories worth a closer look.
>
> Research the last seven days of discussion about AI coding assistants in China. Compare views across platforms and cite the sources.
>
> Add voices from Hacker News, GitHub and Reddit, and generate an offline report.

Login requirements and upstream availability affect coverage. Reports distinguish logged-in results, hot-list matches and public-search fallbacks. Public-search results have no reliable engagement counts or exact dates and do not represent a complete platform sample.

## Little stars, a growing story

Every Star is a small meeting of curious minds. Thanks for keeping this little tool close.

<p align="center">
  <a href="https://github.com/Jesseovo/last30days-skill-cn/stargazers"><img src="https://img.shields.io/github/stars/Jesseovo/last30days-skill-cn?style=flat&amp;label=Stars&amp;labelColor=eee8dc&amp;color=9a7651" alt="GitHub Stars" /></a>&ensp;<a href="https://github.com/Jesseovo/last30days-skill-cn/forks"><img src="https://img.shields.io/github/forks/Jesseovo/last30days-skill-cn?style=flat&amp;label=Forks&amp;labelColor=eee8dc&amp;color=9a7651" alt="GitHub Forks" /></a>
</p>

<p align="center">
  <a href="https://star-history.com/#Jesseovo/last30days-skill-cn&amp;Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Jesseovo/last30days-skill-cn&amp;type=Date&amp;theme=dark" />
      <img src="https://api.star-history.com/svg?repos=Jesseovo/last30days-skill-cn&amp;type=Date" width="680" alt="GitHub Star history for last30days-cn. Click to explore the interactive chart." />
    </picture>
  </a>
</p>

## Keep exploring

[Usage guide](docs/usage.en.md) — Logins, optional dependencies, data paths, configuration and CLI reference.<br />
[Technical specification](SPEC.md) — Retrieval, cleanup, scoring, clustering and output contracts.<br />
[Contributing](AGENTS.md) · [Security](SECURITY.md) · [Release notes](release-notes.md)

## Credits and license

Based on Matt Van Horn's [last30days-skill](https://github.com/mvanhorn/last30days-skill), with Chinese localization by [Jesse](https://github.com/Jesseovo). Thanks to [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) for the reusable-login approach, [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) for its optional service, and [guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) for the research report's visual inspiration.

[MIT License](LICENSE) · [Usage terms](docs/usage.en.md#usage-terms)

---

<p align="center">
  <sub>Made with curiosity, by <a href="https://github.com/Jesseovo">Jesse</a>.</sub><br />
  <sub>If it helped you discover something new, a Star is always welcome.</sub>
</p>
