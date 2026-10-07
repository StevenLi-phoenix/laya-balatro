"""Laya as a Balatro policy: one `choice` question per decision, options = candidate actions.

Inference and training share the same encoding (`Agent._encode_state` + `collate_items`), so a
fine-tuned checkpoint is scored exactly the way it was trained. Only the top encoder layers and
the decision head are trained; the rest of ModernBERT stays frozen to fit an 8 GB GPU.
"""
from __future__ import annotations

import math
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F

import laya
from laya.common import collate_items

from .game import QUESTION

# ModernBERT reads 8k tokens; full-information prompts run ~150-250 state tokens plus up to
# ~450 option tokens, so give both room instead of truncating option lists.
MAX_LEN, HEAD_MAX_LEN = 1024, 480


class Policy:
    def __init__(self, ckpt: str | None = None, train_layers: int = 6, device: str = "cuda"):
        self.agent = laya.load("convaiinnovations/laya", device=device)
        self.model, self.tok, self.device = self.agent.model, self.agent.tok, self.agent.device
        self.model.float()
        enc = self.model.encoder
        self.trainable = (list(enc.layers[-train_layers:]) + [enc.final_norm, self.model.type_emb,
                          self.model.scorer] + ([self.model.head] if self.model.head is not None else []))
        for p in self.model.parameters():
            p.requires_grad_(False)
        for m in self.trainable:
            for p in m.parameters():
                p.requires_grad_(True)
        self.ckpt = ckpt
        if ckpt:
            self.load(ckpt)
        self.model.eval()
        self.opt = None

    # ------------------------------------------------------------------ io
    def trainable_state(self) -> dict:
        names = {id(p) for m in self.trainable for p in m.parameters()}
        return {k: v.detach().cpu() for k, v in self.model.named_parameters() if id(v) in names}

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.trainable_state(), path)
        self.ckpt = path

    def load(self, path: str) -> None:
        missing, unexpected = self.model.load_state_dict(torch.load(path, map_location="cpu"), strict=False)
        assert not unexpected, unexpected
        self.ckpt = path

    # ------------------------------------------------------------------ encoding
    def _items(self, ex: dict) -> list[dict]:
        q = {"type": "choice", "instructions": QUESTION[ex["phase"]], "criteria": list(ex["options"])}
        self.agent._check_question("a", q)
        internal = {"a": self.agent._to_internal(q)}
        return self.agent._encode_state(ex["state"], ["a"], internal, MAX_LEN, HEAD_MAX_LEN)

    def _batch(self, exs: list[dict]):
        groups = [self._items(e) for e in exs]
        b = collate_items(groups, self.tok.pad_token_id)
        dev = self.device
        return (b["input_ids"].to(dev), b["attention_mask"].to(dev), b["marker_pos"].to(dev),
                b["marker_mask"].to(dev), b["qtype"].to(dev))

    def logits(self, exs: list[dict]) -> torch.Tensor:
        with torch.autocast("cuda", dtype=torch.bfloat16):
            lg, _ = self.model(*self._batch(exs))
        return lg.float()

    # ------------------------------------------------------------------ acting
    @torch.no_grad()
    def choose(self, phase: str, state: str, options: list[str], temperature: float = 0.7,
               greedy: bool = False) -> tuple[int, list[float]]:
        if len(options) == 1:
            return 0, [1.0]
        self.model.eval()
        lg = self.logits([{"phase": phase, "state": state, "options": options}])[0, : len(options)]
        p = torch.softmax(lg / max(temperature, 1e-3), -1)
        idx = int(p.argmax()) if greedy else int(torch.multinomial(p, 1))
        return idx, [round(float(x), 4) for x in p]

    # ------------------------------------------------------------------ learning
    def _make_opt(self, lr: float):
        enc_params = [p for m in self.trainable[:-3] for p in m.parameters()]
        head_params = [p for m in self.trainable[-3:] for p in m.parameters()]
        return torch.optim.AdamW([{"params": enc_params, "lr": lr}, {"params": head_params, "lr": lr * 5}],
                                 weight_decay=0.01)

    def train(self, examples: list[dict], epochs: float = 1.0, batch_size: int = 8, lr: float = 2e-5,
              log=print, max_steps: int | None = None, clip: float = 0.2) -> dict:
        """Examples: {phase, state, options, label|labels, ignore?, w?, old_lp?}. Imitation: w>=0 -> w*CE,
        w<0 -> |w| * -log(1 - p_label). Self-play examples carrying old_lp use the PPO clipped
        surrogate with advantage w."""
        if self.opt is None:
            self.opt = self._make_opt(lr)
        steps = int(math.ceil(len(examples) * epochs / batch_size))
        if max_steps:
            steps = min(steps, max_steps)
        warm = max(1, steps // 20)
        sched = torch.optim.lr_scheduler.LambdaLR(
            self.opt, lambda s: min(1.0, (s + 1) / warm) * max(0.05, 1 - s / max(1, steps)))
        self.model.train()
        order = []
        t0, run_loss, run_acc, n = time.time(), 0.0, 0.0, 0
        for step in range(steps):
            if len(order) < batch_size:
                order += random.sample(range(len(examples)), len(examples))
            batch = [examples[order.pop()] for _ in range(batch_size)]
            lg = self.logits(batch)
            ok = self._label_mask(batch, lg.shape[1])
            w = torch.tensor([e.get("w", 1.0) for e in batch], device=self.device, dtype=torch.float32)
            # `ignore`: options a label neither rewards nor punishes (search labels say nothing about
            # using a consumable mid-hand), left out of the softmax the label is judged in
            ign = torch.zeros_like(ok)
            for r, e in enumerate(batch):
                for k in e.get("ignore") or ():
                    ign[r, k] = True
            logp = F.log_softmax(lg.masked_fill(ign & ~ok, -1e4), -1)
            lp = logp.masked_fill(~ok, -1e4).logsumexp(-1)  # log P(any correct option)
            neg = torch.log1p(-lp.exp().clamp(max=1 - 1e-4))
            per = torch.where(w >= 0, -w * lp, w.abs() * -neg)
            if any("old_lp" in e for e in batch):
                # Self-play: PPO clipped surrogate. The advantage w moves p(click) at most +-clip
                # relative to the policy that played the game, so one iteration cannot drag
                # confident correct clicks (e.g. "play selected") down because a round was lost.
                has = torch.tensor(["old_lp" in e for e in batch], device=self.device)
                old = torch.tensor([e.get("old_lp", 0.0) for e in batch], device=self.device)
                ratio = (lp - old).exp()
                ppo = -torch.minimum(ratio * w, ratio.clamp(1 - clip, 1 + clip) * w)
                per = torch.where(has, ppo, per)
            loss = per.mean()
            self.opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for m in self.trainable for p in m.parameters()], 1.0)
            self.opt.step()
            sched.step()
            run_loss += float(loss)
            run_acc += float(ok.gather(1, lg.argmax(-1, keepdim=True)).float().mean())
            n += 1
            if (step + 1) % 50 == 0 or step + 1 == steps:
                log(f"  step {step + 1}/{steps} loss {run_loss / n:.4f} acc {run_acc / n:.3f} "
                    f"{(time.time() - t0) / (step + 1):.2f}s/step")
                run_loss = run_acc = 0.0
                n = 0
        self.model.eval()
        self.opt = None  # fresh optimizer per generation keeps memory flat between phases
        torch.cuda.empty_cache()
        return {"steps": steps}

    def _label_mask(self, batch: list[dict], n: int) -> torch.Tensor:
        """[B, n] bool: the correct option(s). `labels` (several acceptable clicks) or `label`."""
        ok = torch.zeros(len(batch), n, dtype=torch.bool, device=self.device)
        for r, e in enumerate(batch):
            for k in e.get("labels") or [e["label"]]:
                ok[r, k] = True
        return ok

    @torch.no_grad()
    def evaluate(self, examples: list[dict], batch_size: int = 16) -> dict:
        self.model.eval()
        by_phase: dict[str, list[int]] = {}
        for i in range(0, len(examples), batch_size):
            batch = examples[i: i + batch_size]
            pred = self.logits(batch).argmax(-1).tolist()
            for e, p in zip(batch, pred):
                by_phase.setdefault(e["phase"], []).append(int(p in (e.get("labels") or [e["label"]])))
        out = {k: round(sum(v) / len(v), 3) for k, v in by_phase.items()}
        out["all"] = round(sum(sum(v) for v in by_phase.values()) / max(1, sum(len(v) for v in by_phase.values())), 3)
        return out
