# GitHub Wiki Setup Instructions

GitHub wikis are a separate Git repository that lives alongside your main repository. Here's how to set up your documentation as a GitHub wiki:

## Option 1: Enable Wiki Through GitHub UI (Easiest)

1. **Enable Wiki:**
   - Go to your GitHub repository
   - Click on "Settings" tab
   - Scroll down to "Features" section
   - Check the box next to "Wikis"

2. **Create Wiki Pages:**
   - Click on "Wiki" tab in your repository
   - Click "Create the first page"
   - Name it "Home" (this will be the landing page)
   
3. **Add Documentation Pages:**
   - Click "New Page" button
   - Create pages with these names:
     - `Home` - Overview and navigation
     - `Mod-Author-Guide` - Content from MOD_AUTHOR_GUIDE.md
     - `Mod-Requirements` - Content from MOD_REQUIREMENTS.md
   - Copy and paste the markdown content from your files
   - Click "Save Page"

## Option 2: Clone Wiki Repository and Push (Advanced)

1. **Enable Wiki** (same as Option 1, step 1)

2. **Clone the wiki repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO.wiki.git
   cd YOUR_REPO.wiki
   ```

3. **Copy your documentation files:**
   ```bash
   # Copy files and rename them for wiki format
   cp ../MOD_AUTHOR_GUIDE.md ./Mod-Author-Guide.md
   cp ../MOD_REQUIREMENTS.md ./Mod-Requirements.md
   cp ../README.md ./Home.md
   ```

4. **Edit Home.md** to create a landing page with navigation:
   ```markdown
   # Mewtator Wiki
   
   Welcome to the Mewtator documentation!
   
   ## Documentation
   
   - [Mod Author Guide](Mod-Author-Guide) - Learn how to create mods
   - [Mod Requirements](Mod-Requirements) - Detailed guide on the requirements system
   
   ## Quick Links
   
   - [Download on Nexus Mods](https://www.nexusmods.com/mewgenics/mods/1)
   - [Main Repository](https://github.com/YOUR_USERNAME/YOUR_REPO)
   ```

5. **Push to wiki:**
   ```bash
   git add .
   git commit -m "Add documentation pages"
   git push origin master
   ```

## Option 3: Automated Sync (Most Advanced)

You can set up a GitHub Action to automatically sync your documentation files to the wiki when they change:

1. Create `.github/workflows/wiki-sync.yml` in your main repository:
   ```yaml
   name: Sync Wiki
   
   on:
     push:
       branches:
         - main
       paths:
         - 'MOD_AUTHOR_GUIDE.md'
         - 'MOD_REQUIREMENTS.md'
         - 'README.md'
   
   jobs:
     sync:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         
         - name: Sync to Wiki
           uses: Andrew-Chen-Wang/github-wiki-action@v4
           env:
             WIKI_CONTENT_DIR: ./
             GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
             GH_MAIL: github-actions@github.com
             GH_NAME: github-actions
   ```

2. This will automatically update your wiki whenever you push changes to these documentation files

## Recommended Approach

**For your use case, I recommend Option 1** because:
- It's the simplest and fastest to set up
- You maintain the source files in your main repository
- Easy to update - just edit on GitHub
- No extra automation complexity

**Steps to follow:**
1. Enable Wiki in repository settings
2. Create three pages: Home, Mod-Author-Guide, Mod-Requirements
3. Copy content from your .md files
4. Update internal links (e.g., change `[MOD_REQUIREMENTS.md](MOD_REQUIREMENTS.md)` to `[Mod Requirements](Mod-Requirements)`)

## Wiki Link Format

In GitHub wikis, links work differently:
- Instead of: `[MOD_REQUIREMENTS.md](MOD_REQUIREMENTS.md)`
- Use: `[Mod Requirements](Mod-Requirements)`
- Wiki pages don't need the `.md` extension in links

## Maintaining Both

You can maintain documentation in both places:
- Keep `.md` files in repository for developers and contributors
- Mirror content in Wiki for easier browsing
- Update wiki manually when documentation changes (or use Option 3 for automation)

## Notes

- Wiki repositories are separate from your main repository
- They have their own commit history
- Anyone with write access to your repo can edit the wiki
- You can restrict wiki editing in repository settings (Settings > Features > Wikis > "Restrict editing to collaborators only")
