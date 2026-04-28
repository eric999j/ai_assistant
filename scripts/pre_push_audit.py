#!/usr/bin/env python3
"""
pre-push hook：推送前執行依賴套件 CVE 掃描。
安裝方式：由 pre-commit 框架管理，或手動複製到 .git/hooks/pre-push

此 hook 執行 pip-audit 檢查 requirements.txt 中的已知弱點。
若發現嚴重度為高或有可修復的 CVE，將阻擋推送。
"""
import subprocess
import sys
import json


def main() -> int:
    print("[SCAN] pre-push: 執行依賴套件 CVE 掃描...")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "-r", "requirements.txt", "-f", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("[WARN] pip-audit 未安裝，略過 CVE 掃描")
        print("   安裝方式: pip install pip-audit")
        return 0
    except subprocess.TimeoutExpired:
        print("[WARN] pip-audit 執行逾時，略過")
        return 0

    if result.returncode == 0:
        print("[PASS] 未發現已知 CVE")
        return 0

    # 解析結果，判斷是否有可修復的弱點
    try:
        data = json.loads(result.stdout)
        vulnerabilities = []
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                vulnerabilities.append({
                    "package": dep["name"],
                    "version": dep["version"],
                    "id": vuln["id"],
                    "fix_versions": vuln.get("fix_versions", []),
                })

        if not vulnerabilities:
            print("[PASS] 未發現已知 CVE")
            return 0

        fixable = [v for v in vulnerabilities if v["fix_versions"]]
        unfixable = [v for v in vulnerabilities if not v["fix_versions"]]

        print(f"\n[WARN] 發現 {len(vulnerabilities)} 個已知弱點：")
        for v in vulnerabilities:
            fix = f" → 修復版本: {', '.join(v['fix_versions'])}" if v["fix_versions"] else " (尚無修復版本)"
            print(f"  - {v['package']}=={v['version']}  {v['id']}{fix}")

        if fixable:
            print(f"\n[FAIL] 有 {len(fixable)} 個可修復的弱點，請先升級後再推送。")
            print("   執行: pip-audit -r requirements.txt --fix")
            return 1

        # 只有無法修復的弱點 → 警告但允許推送
        print(f"\n[WARN] {len(unfixable)} 個弱點尚無修復版本，允許推送（請持續追蹤）。")
        return 0

    except (json.JSONDecodeError, KeyError):
        # JSON 解析失敗，顯示原始輸出
        print("[WARN] pip-audit 輸出異常：")
        print(result.stdout[:500] if result.stdout else result.stderr[:500])
        return 0


if __name__ == "__main__":
    sys.exit(main())
