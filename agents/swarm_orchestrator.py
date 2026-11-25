import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
from .agent1_chat import ChatLanguageAgent
from .agent2_commander import CommanderAgent
from .agent3_scanner import DeepScannerAgent
from .agent4_accelerator import GitHubAcceleratorAgent


class SwarmOrchestrator:
    def __init__(self):
        self.agent1 = ChatLanguageAgent()
        self.agent2 = CommanderAgent()
        self.agent3 = DeepScannerAgent()
        self.agent4 = GitHubAcceleratorAgent()

    def verify_all(self) -> Dict[str, object]:
        chat_probe = self.agent1.suggest_context("اشرح ثغرات apk", top_k=1)
        route_probe = self.agent2.route("افحص ملف apk واستخرج الثغرات")
        return {
            "agent1_loaded": len(self.agent1.memory) > 0,
            "agent1_samples": len(self.agent1.memory),
            "agent1_probe_ok": len(chat_probe) > 0,
            "agent2_loaded": len(self.agent2.class_priors) >= 4,
            "agent2_route_ok": route_probe.get("intent") == "scan_apk",
            "agent3_loaded": len(self.agent3.rules) >= 10,
            "agent3_rules": len(self.agent3.rules),
            "agent4_loaded": bool(self.agent4.profile),
            "agent4_models_ok": not bool(self.agent4.profile.get("models_gitignored", False)),
        }

    def run_swarm(
        self,
        user_message: str,
        workspace_dir: Optional[Path] = None,
    ) -> Dict[str, object]:
        route_plan = self.agent2.route(user_message)
        hints = self.agent1.suggest_context(user_message, top_k=2)
        apk_findings: List[Dict[str, object]] = []
        if workspace_dir and workspace_dir.exists():
            for apk in list(workspace_dir.rglob("*.apk"))[:2]:
                res = self.agent3.inspect_apk(apk)
                apk_findings.extend(res.get("findings", []))
        return {
            "route_plan": route_plan,
            "chat_hints": hints,
            "apk_findings": apk_findings[:15],
            "speed_profile": self.agent4.profile,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    swarm = SwarmOrchestrator()
    if args.verify:
        status = swarm.verify_all()
        print("Swarm Verification:", json.dumps(status, ensure_ascii=False))
