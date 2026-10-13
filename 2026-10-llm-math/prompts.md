# Prompts

## Initial version, 13 Oct 2026

<!-- llmmath multiplication evals 2026-10: https://chatgpt.com/c/6acdd336-5228-83ec-a6ca-b801a2f6966d (2026-10-13T17:13:06+08:00) -->

I'd like to get a sense of how large a set of numbers frontier models today are able to multiply. If we ask them, let's say 10 times to multiply 8-digit numbers, 12-digit numbers, 15-digit numbers, and so on. At what point do they reliably start failing? What I'd like you to do is write and run a program to test these model capabilities on my machine and share the results.

Use [LocalMCP2](/plugins/plugin_asdk_app_6ab0b6c561508191882e58b23665db3e) and OpenRouter models and API keys and whatever else you need.

---

First, give me a quick sense of what this cost, please.

Next: did this complete? If not, could you please complete it? Also, move these into a reproducible structure under ~/code/research/2026-10-llm-math/

Make sure that there's a script that, when just build is run, it reproduces the output. Copy the existing output so that if I re-run it, it will instantly exit because all output is there, but if I delete the output(s) it will re-run, and if interrupted, will continue from where it left off. If possible, capture costs as well.

Document results, then process, and any other things, in README.md.

---

I've changed my mind on the folder location. Let's move it to ~/code/llmevals/2026-10-llm-math/ but the rest can stay the same. Update ~/code/llmevals/README.md as well.

---

I ran just retry-credits and it completed. Any changes to be made anywhere? Update what's required. Then stage files for commit (with a .gitignore on what needn't be committed.)
