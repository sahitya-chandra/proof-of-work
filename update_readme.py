from github import Github, Auth
from dotenv import load_dotenv
import os, json
from collections import defaultdict

load_dotenv()

auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
g = Github(auth=auth)

config_file = ""
orgs_to_track = []
if os.path.exists(config_file):
    with open(config_file, "r") as f:
        config = json.load(f)
        orgs_to_track = config.get("organizations", [])
else:
    print("Warning: config.json not found. Fetching PRs from all organizations.")

role = ['MEMBER', 'CONTRIBUTOR']
user = g.get_user()
username = user.login
query = f"author:{username} type:pr"
prs_by_org = defaultdict(list)

try:
    prs = g.search_issues(query=query)
    for pr in prs:
        if pr.author_association in role:
            org_name = pr.repository.full_name.split("/")[0]
            if not orgs_to_track or org_name in orgs_to_track:
                repo = g.get_repo(pr.repository.full_name)
                full_pr = repo.get_pull(pr.number)
                prs_by_org[org_name].append({
                    "repo": pr.repository.name,
                    "full_name": pr.repository.full_name,
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state.capitalize(),
                    "url": pr.html_url,
                    "created_at": pr.created_at.strftime("%Y-%m-%d"),
                    "merged_at": full_pr.merged_at.strftime("%Y-%m-%d") if full_pr.merged_at else None
                })
except Exception as e:
    print(f"Err fetcing PRs: {e}")
    exit(1)
      

readme_content = "# Proof of Work\n\nMy open-source contributions to public organizations.\n\n"


total_prs = sum(len(prs) for prs in prs_by_org.values())
merged_prs = sum(
    len([pr for pr in prs if pr["merged_at"] is not None])
    for prs in prs_by_org.values()
)
readme_content += f"**Total PRs**: {total_prs} | **Merged PRs**: {merged_prs}\n\n"

for org, prs in sorted(prs_by_org.items()):
    if prs:
        readme_content += f"## Organization: {org}\n"
        readme_content += "| Repository | PR Title | Status | Created At | Merged At | Link |\n"
        readme_content += "|------------|----------|--------|------------|-----------|------|\n"
        for pr in sorted(prs, key=lambda x: x["created_at"], reverse=True):
            readme_content += f"| {pr['repo']} | {pr['title']} | {pr['state']} | {pr['created_at']} | {pr['merged_at']} | [PR #{pr['number']}]({pr['url']}) |\n"
        readme_content += "\n"

with open("README.md", "w") as f:
    f.write(readme_content)

print("README.md updated successfully!")

g.close()
# my_prs = [pr for pr in prs if pr.author_association == 'CONTRIBUTOR']
#   print(f"[{pr.repository.full_name}] PR #{pr.number}: {pr.title} [{pr.state}] -> {pr.html_url}")
