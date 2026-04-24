"""
System requirements checker
Run this before setup to verify all prerequisites are installed
"""

import subprocess
import sys
import platform


def check_command(command, min_version=None, name=None):
    """Check if a command is available"""
    display_name = name or command
    try:
        result = subprocess.run(
            [command, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        version_output = result.stdout + result.stderr

        if min_version:
            print(f"✓ {display_name} is installed: {version_output.split()[0]}")
        else:
            print(f"✓ {display_name} is installed")

        return True

    except FileNotFoundError:
        print(f"✗ {display_name} is NOT installed")
        return False
    except Exception as e:
        print(f"? {display_name} check failed: {e}")
        return False


def check_postgres():
    """Check PostgreSQL installation"""
    commands_to_try = ['psql', 'postgres']

    for cmd in commands_to_try:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✓ PostgreSQL is installed: {version}")
                return True
        except FileNotFoundError:
            continue
        except Exception:
            continue

    print("✗ PostgreSQL is NOT installed")
    return False


def check_python_packages():
    """Check if required Python packages can be imported"""
    packages = {
        'fastapi': 'FastAPI',
        'sqlalchemy': 'SQLAlchemy',
        'openai': 'OpenAI',
        'pgvector': 'pgvector',
    }

    print("\nChecking Python packages (from backend/requirements.txt)...")
    all_installed = True

    for package, display_name in packages.items():
        try:
            __import__(package)
            print(f"  ✓ {display_name}")
        except ImportError:
            print(f"  ✗ {display_name} - run: pip install -r backend/requirements.txt")
            all_installed = False

    return all_installed


def main():
    print("=" * 60)
    print("Roblox Discovery - Requirements Check")
    print("=" * 60)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    print("=" * 60)
    print()

    results = {}

    # Check Python
    print("Checking system requirements...")
    print()

    python_version = sys.version_info
    if python_version >= (3, 9):
        print(f"✓ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        results['python'] = True
    else:
        print(f"✗ Python version too old: {python_version.major}.{python_version.minor}")
        print("  Requires Python 3.9+")
        results['python'] = False

    # Check Node.js
    results['node'] = check_command('node', name='Node.js')

    # Check npm
    results['npm'] = check_command('npm', name='npm')

    # Check PostgreSQL
    results['postgres'] = check_postgres()

    # Check Git (optional but recommended)
    results['git'] = check_command('git', name='Git (optional)')

    print()
    print("=" * 60)

    # Summary
    required_items = ['python', 'node', 'npm', 'postgres']
    all_required_installed = all(results.get(item, False) for item in required_items)

    if all_required_installed:
        print("✓ All required dependencies are installed!")
        print()
        print("Next steps:")
        print("  1. Set up backend: cd backend && python -m venv venv")
        print("  2. Install packages: pip install -r requirements.txt")
        print("  3. Initialize database: python init_db.py")
        print("  4. Set up frontend: cd frontend && npm install")
        print()
        print("See QUICKSTART.md for detailed instructions")

    else:
        print("✗ Some required dependencies are missing")
        print()
        print("Please install missing items:")

        if not results.get('python'):
            print("  - Python 3.9+: https://www.python.org/downloads/")

        if not results.get('node'):
            print("  - Node.js 18+: https://nodejs.org/")

        if not results.get('postgres'):
            print("  - PostgreSQL 14+:")
            if platform.system() == 'Darwin':
                print("    macOS: brew install postgresql")
            elif platform.system() == 'Linux':
                print("    Linux: sudo apt install postgresql")
            elif platform.system() == 'Windows':
                print("    Windows: https://www.postgresql.org/download/windows/")

    print("=" * 60)


if __name__ == "__main__":
    main()
