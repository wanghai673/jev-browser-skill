"""Exclude consecutive repeated operations that produce no observable progress."""

import json


def progress_signature(page):
    # Ignore geometry jitter, action numbering and advancing playback time.
    # Keep control values, document/tab identity and meaningful media state.
    content = {k: page.get(k) for k in ("url", "title", "tab_id", "document_id", "text", "scroll")}
    content["actions"] = [
        {k: v for k, v in action.items() if k not in {"id", "rect"}} for action in page.get("actions", [])
    ]
    content["media"] = [{k: v for k, v in media.items() if k != "current_time"} for media in page.get("media", [])]
    return json.dumps(content, sort_keys=True)


class RepetitionGuard:
    def __init__(self, limit=3):
        self.limit = limit
        self.excluded = set()
        self.reset()

    def reset(self):
        self.key = None
        self.signature = None
        self.count = 0

    def option_key(self, page, action):
        return (
            page.get("tab_id"), page.get("document_id"), page.get("url"),
            action["kind"], action.get("node", action.get("id")),
            action.get("href"), action.get("value"), action.get("delta"),
        )

    def available_page(self, page):
        return {**page, "actions": [
            action for action in page.get("actions", [])
            if self.option_key(page, action) not in self.excluded
        ]}

    def record(self, action, before, after, text=None):
        previous, current = progress_signature(before), progress_signature(after)
        if action["kind"] == "wait" or previous != current:
            self.reset()
            return None
        key = (
            action["kind"],
            action.get("node", action.get("id")),
            action.get("href"),
            action.get("value"),
            action.get("delta"),
            text,
        )
        self.count = self.count + 1 if key == self.key and previous == self.signature else 1
        self.key, self.signature = key, current
        if self.count < self.limit:
            return None
        self.excluded.add(self.option_key(before, action))
        return {
            "code": "repeated_action_no_progress",
            "kind": action["kind"],
            "action": action["label"],
            "count": self.count,
            "limit": self.limit,
            "url": after["url"],
        }
