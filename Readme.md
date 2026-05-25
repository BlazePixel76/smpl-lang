# ⚡ Simple Multi-Purpose Logic (SMPL)

```text
  ____  __  __ ____  _     
 / ___||  \/  |  _ \| |    
 \___ \| |\/| | |_) | |    
  ___) | |  | |  __/| |___ 
 |____/|_|  |_|_|   |_____|
```

SMPL is a lightweight, cross-platform interpreted scripting language designed for fast terminal automation, desktop utility workflows, and persistent session state.

It removes structural noise, excessive syntax, and boilerplate so your scripts stay readable, intuitive, and easy to build.

## ✨ Key Features
- **Zero-Friction I/O** — `speak` and `listen` replace verbose string handling.
- **Native State Persistence** — built-in `save`, `load`, and `forget` let your scripts persist session state without extra plumbing.
- **Cross-Platform OS Bridge** — `open` and `run` support desktop automation across Windows, Linux, and macOS.
- **Clean Control Flow** — intuitive `if/then/otherwise then` syntax keeps logic readable.
- **Task Arguments & Returns** — tasks can accept inputs and return values with `give`.
- **List Support** — arrays make inventories, path lists, and compound state easy.

## 🚀 Quick Start

### Example: basic interaction

```smpl
speak "What is your name? "
listen name
speak "Hello "
speak name
```

## 🧠 Language Highlights

### Flattened conditional chaining

```smpl
if command == 1
then speak "One"
otherwise if command == 2
then speak "Two"
otherwise
then speak "Unknown"
```

### Task arguments and return values

```smpl
task add the a b then
    set result = a + b
    give result
    stop

set total = add 5 7
speak total
```

### Lists and indexing

```smpl
set inventory = ["sword", "shield", "potion"]
speak inventory[0]
set inventory[0] = "mega_sword"
speak inventory[0]
```

## 🛠️ Installation & Execution

### Windows

1. Clone this repository to a permanent location, for example `C:\SMPL`.
2. Add that folder to your Windows PATH.
3. Run scripts from any terminal using:

```powershell
smpl.bat dashboard.smpl
```

If you want `smpl` directly from PowerShell, keep `smpl.bat` on your PATH.

### Linux / macOS

1. Clone the repository and `cd` into the root directory.
2. Make the wrapper executable:

```bash
chmod +x smpl
```

3. Optional: install the launcher globally:

```bash
sudo ln -s "$(pwd)/smpl" /usr/local/bin/smpl
```

4. Run scripts with:

```bash
./smpl dashboard.smpl
```

or once installed globally:

```bash
smpl dashboard.smpl
```

## 💡 VS Code Syntax Highlighting

For lightweight `.smpl` highlighting in VS Code, add this to your user settings JSON:

```json
"files.associations": {
  "*.smpl": "ini"
}
```

## 📄 License

SMPL is distributed under the MIT License.

---

Once `Readme.md` is saved, your project documentation is ready. Open the VS Code terminal (**Ctrl + `**) and I’ll help you verify the launcher commands next.
