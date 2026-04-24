from github import Github, Auth, InputFileContent
from dotenv import load_dotenv
import os
from collections import defaultdict
from datetime import datetime, timedelta

load_dotenv()

token = os.getenv("GITHUB_TOKEN")
g = Github(auth=Auth.Token(token))

user = g.get_user()
username = user.login
print(f"Fetching PRs for: {username}")

two_years_ago = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
query = f"author:{username} type:pr created:>={two_years_ago}"

# PRs closed on GitHub but commits were applied directly to main by the maintainer
INDIRECT_MERGES = {
    "osdldbt/dbt5#29",
    "pgmoneta/pgmoneta_mcp#97",
}

EXCLUDE_ORGS = {
    "PalisadoesFoundation",
    "antiwork",
    "asyncapi",
    "code100x",
    "dubinc",
    "json-schema-org",
    "mrhashcoder",
}

print(f"Search query: {query}")

def is_quality_pr(full_pr, pr_issue, org_name):
    merged = full_pr.merged_at is not None
    comments = (pr_issue.comments or 0) + (full_pr.review_comments or 0)

    # All merged calcom PRs — primary contribution org
    if org_name.lower() == "calcom" and merged:
        return True

    # For everything else: merged PRs are good by default
    if merged:
        return True

    # Open or closed: only if there's real engagement (discussion/review happened)
    if comments >= 2:
        return True

    return False

prs_by_org = defaultdict(list)
total_fetched = 0
total_included = 0

print("Fetching PRs...")
prs = g.search_issues(query=query)

for pr in prs:
    total_fetched += 1
    org_name = pr.repository.full_name.split("/")[0]

    if org_name in EXCLUDE_ORGS or org_name == username:
        print(f"  [x] excluded {pr.repository.full_name} #{pr.number}")
        continue

    try:
        repo = g.get_repo(pr.repository.full_name)
        full_pr = repo.get_pull(pr.number)

        pr_key = f"{pr.repository.full_name}#{pr.number}"
        indirect = pr_key in INDIRECT_MERGES

        if indirect or is_quality_pr(full_pr, pr, org_name):
            total_included += 1
            if indirect:
                state = "Merged (indirect)"
                merged_at = pr.closed_at.strftime("%Y-%m-%d") if pr.closed_at else None
            elif full_pr.merged_at:
                state = "Merged"
                merged_at = full_pr.merged_at.strftime("%Y-%m-%d")
            else:
                state = pr.state.capitalize()
                merged_at = None

            prs_by_org[org_name].append({
                "repo": pr.repository.name,
                "full_name": pr.repository.full_name,
                "number": pr.number,
                "title": pr.title,
                "state": state,
                "url": pr.html_url,
                "created_at": pr.created_at.strftime("%Y-%m-%d"),
                "merged_at": merged_at,
                "comments": (pr.comments or 0) + (full_pr.review_comments or 0),
            })
            print(f"  [+] {pr.repository.full_name} #{pr.number} ({prs_by_org[org_name][-1]['state']})")
        else:
            print(f"  [-] skipped {pr.repository.full_name} #{pr.number} (state={pr.state}, comments={pr.comments})")

    except Exception as e:
        print(f"  [!] Error on {pr.repository.full_name} #{pr.number}: {e}")

print(f"\nFetched: {total_fetched} | Included: {total_included}")

# ── Build gist markdown ────────────────────────────────────────────────────────

total_merged = sum(
    sum(1 for p in prs if p["state"] in ("Merged", "Merged (indirect)")) for prs in prs_by_org.values()
)
total_open = sum(
    sum(1 for p in prs if p["state"] == "Open") for prs in prs_by_org.values()
)
total_closed = sum(
    sum(1 for p in prs if p["state"] == "Closed") for prs in prs_by_org.values()
)

lines = []
lines.append("# Open Source Contributions (2024–2026)")
lines.append("")
lines.append("> Curated pull requests from the last 2 years across public organizations.")
lines.append("")
lines.append(f"**{total_included} PRs** — {total_merged} Merged · {total_open} Open · {total_closed} Closed")
lines.append("")

# Cal.com first — primary org
priority_orgs = ["calcom"]
other_orgs = sorted(o for o in prs_by_org if o not in priority_orgs)
ordered_orgs = [o for o in priority_orgs if o in prs_by_org] + other_orgs

for org in ordered_orgs:
    prs_list = sorted(prs_by_org[org], key=lambda x: x["created_at"], reverse=True)
    merged_count = sum(1 for p in prs_list if p["state"] in ("Merged", "Merged (indirect)"))

    lines.append(f"## {org}  ({len(prs_list)} PRs, {merged_count} merged)")
    lines.append("")
    lines.append("| # | Repository | Title | Status | Date | Merged |")
    lines.append("|---|------------|-------|--------|------|--------|")

    for p in prs_list:
        title = p["title"].replace("|", "\\|")
        merged_at = p["merged_at"] or "—"
        status_badge = {"Merged": "✅ Merged", "Merged (indirect)": "✅ Merged (indirect)", "Open": "🔵 Open", "Closed": "❌ Closed"}.get(p["state"], p["state"])
        lines.append(
            f"| [#{p['number']}]({p['url']}) | {p['repo']} | {title} | {status_badge} | {p['created_at']} | {merged_at} |"
        )

    lines.append("")

gist_content = "\n".join(lines)

# ── Create the gist ────────────────────────────────────────────────────────────

GIST_ID = "4dc5097ee57ce159b8d32e050b843be9"

print("\nUpdating gist...")
gist = g.get_gist(GIST_ID)
gist.edit(
    description="Open Source Contributions — Proof of Work (2024–2026)",
    files={"open-source-contributions.md": InputFileContent(gist_content)},
)

print(f"\nGist updated: {gist.html_url}")
