"""Bounded observations for this call only; no inferred completion and no disk state."""

from collections import OrderedDict
from copy import deepcopy


class TaskEvidence:
    def __init__(self, page_limit=8):
        self.pages = OrderedDict()
        self.navigation = OrderedDict()
        self.page_limit = page_limit

    def record(self, page, history):
        url = page["url"]
        controls = []
        for action in page.get("actions", []):
            state = {k: action[k] for k in ("checked", "selected", "current_value") if k in action}
            if action.get("kind") == "fill" and action.get("value"):
                state["value"] = action["value"]
            if state:
                control = {"label": action.get("label", ""), **state}
                if control not in controls:
                    controls.append(control)
        snapshot = {
            "url": url,
            "title": page.get("title", ""),
            "observed_after_action": len(history),
            "visible_text": page.get("text", "")[:2400],
            "controls": controls[:20],
            "media": page.get("media", []),
        }
        self.pages[url] = deepcopy(snapshot)
        self.pages.move_to_end(url)
        while len(self.pages) > self.page_limit:
            self.pages.popitem(last=False)
        if history:
            action = history[-1]
            source = action.get("source_url")
            if source and source != url and action.get("kind") in {"click", "fill", "select"}:
                key = (len(history), url)
                self.navigation[key] = {
                    "after_action": len(history),
                    "action": action["action"],
                    "from_url": source,
                    "target_url": action.get("target_url"),
                    "to_url": url,
                }
                while len(self.navigation) > self.page_limit:
                    self.navigation.popitem(last=False)

    def context(self, current_url):
        # The current page is already supplied separately. Keep earlier pages available across steps.
        return deepcopy(
            {
                "observed_pages": [p for url, p in self.pages.items() if url != current_url],
                "navigation": list(self.navigation.values()),
            }
        )
