"""Test GameImporter initialization"""
import sys
import traceback
sys.path.insert(0, '.')

try:
    print("Testing GameImporter instantiation...")
    from app.services.game_importer import GameImporter

    importer = GameImporter()
    print("SUCCESS: GameImporter created")
    print(f"  - generate_embeddings: {importer.generate_embeddings}")
    print(f"  - generate_llm_enrichment: {importer.generate_llm_enrichment}")
    print(f"  - embedding_service: {importer.embedding_service is not None}")
    print(f"  - llm_service: {importer.llm_service is not None}")

except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
