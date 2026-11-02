#!/usr/bin/env python3
import argparse
import sys
import os
import requests
import json
from tabulate import tabulate
from getpass import getpass

API_BASE = os.getenv("KRAVIGIL_API_URL", "http://localhost/api/v1")
TOKEN_FILE = os.path.expanduser("~/.kravigil_token")

def login(args):
    email = args.email or input("Email: ")
    password = getpass("Password: ")

    res = requests.post(f"{API_BASE}/auth/login", data={"username": email, "password": password})
    if res.status_code == 200:
        token = res.json()["access_token"]
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print("[+] Logged in successfully.")
    else:
        print(f"[-] Login failed: {res.text}")
        sys.exit(1)

def get_headers():
    if not os.path.exists(TOKEN_FILE):
        print("[-] Not authenticated. Run 'kravigil login' first.")
        sys.exit(1)
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()
    return {"Authorization": f"Bearer {token}"}

def list_targets(args):
    res = requests.get(f"{API_BASE}/targets/", headers=get_headers())
    if res.status_code == 200:
        targets = res.json()
        if not targets:
            print("No targets found.")
            return
        table = [[t["id"][:8], t["name"], t["ip_address"] or t["domain"], t["is_authorized"]] for t in targets]
        print(tabulate(table, headers=["ID", "Name", "IP/Domain", "Authorized"], tablefmt="grid"))
    else:
        print(f"[-] Error: {res.text}")

def create_target(args):
    payload = {
        "name": args.name,
        "ip_address": args.ip,
        "domain": args.domain,
        "is_authorized": args.authorized
    }
    res = requests.post(f"{API_BASE}/targets/", json=payload, headers=get_headers())
    if res.status_code == 201:
        print(f"[+] Target '{args.name}' created successfully.")
    else:
        print(f"[-] Error: {res.text}")

def start_scan(args):
    payload = {
        "target_id": args.target_id,
        "ports": [int(p) for p in args.ports.split(",")] if args.ports else [22, 80, 443]
    }
    endpoint = "network" if args.type == "network" else "web"
    res = requests.post(f"{API_BASE}/scans/{endpoint}", json=payload, headers=get_headers())
    if res.status_code == 202:
        print(f"[+] Scan started successfully. Scan ID: {res.json()['id']}")
    else:
        print(f"[-] Error: {res.text}")

def list_findings(args):
    url = f"{API_BASE}/findings/?limit=50"
    if args.severity:
        url += f"&severity={args.severity}"

    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        findings = res.json()
        if not findings:
            print("No findings found.")
            return
        table = [[f["id"][:8], f["title"], f["severity"], f["confidence"], f["cve_id"] or "-"] for f in findings]
        print(tabulate(table, headers=["ID", "Title", "Severity", "Confidence", "CVE"], tablefmt="grid"))
    else:
        print(f"[-] Error: {res.text}")

def main():
    parser = argparse.ArgumentParser(description="KRAVIGIL CLI")
    subparsers = parser.add_subparsers(dest="command")

    login_parser = subparsers.add_parser("login")
    login_parser.add_argument("--email", help="Admin email")
    login_parser.set_defaults(func=login)

    subparsers.add_parser("list-targets").set_defaults(func=list_targets)

    create_target_parser = subparsers.add_parser("create-target")
    create_target_parser.add_argument("--name", required=True)
    create_target_parser.add_argument("--ip")
    create_target_parser.add_argument("--domain")
    create_target_parser.add_argument("--authorized", action="store_true")
    create_target_parser.set_defaults(func=create_target)

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("target_id")
    scan_parser.add_argument("--type", choices=["network", "web"], default="network")
    scan_parser.add_argument("--ports", help="Comma-separated ports (e.g., 22,80,443)")
    scan_parser.set_defaults(func=start_scan)

    findings_parser = subparsers.add_parser("findings")
    findings_parser.add_argument("--severity", choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    findings_parser.set_defaults(func=list_findings)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
