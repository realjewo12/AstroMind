"""
test_knowledge.py

Integration test for the Day 3 knowledge layer.

Tests
-----
1. similarity_search() returns exactly k=3 Documents
2. Each Document has non-empty page_content
3. Each Document carries a "source" metadata key
4. Re-running get_vectorstore() does NOT duplicate chunks in the DB
"""

import sys
from knowledge.vectorstore import get_vectorstore, similarity_search


def test_similarity_search():
    print("\n[TEST 1] similarity_search('crew stress management', k=3)")

    results = similarity_search("crew stress management", k=3)

    # Must return exactly 3 chunks
    assert len(results) == 3, (
        f"Expected 3 results, got {len(results)}"
    )

    for i, doc in enumerate(results):
        # Each chunk must have actual text
        assert doc.page_content.strip(), (
            f"Chunk {i} has empty page_content"
        )

        # Each chunk must know which file it came from
        assert "source" in doc.metadata, (
            f"Chunk {i} missing 'source' in metadata"
        )

        print(f"  Chunk {i+1}: [{doc.metadata['source']}] "
              f"{doc.page_content[:120].strip()!r}...")

    print("[TEST 1] PASSED")


def test_no_duplicate_ingestion():
    print("\n[TEST 2] Re-ingestion guard — second call must not grow the DB")

    vs = get_vectorstore()
    count_before = vs._collection.count()
    print(f"  Chunk count before second call: {count_before}")

    # Call get_vectorstore() again — should hit the singleton, not re-ingest
    vs2 = get_vectorstore()
    count_after = vs2._collection.count()
    print(f"  Chunk count after  second call: {count_after}")

    assert count_before == count_after, (
        f"Re-ingestion occurred: count grew from {count_before} to {count_after}"
    )

    print("[TEST 2] PASSED")


def main():
    print("=" * 60)
    print("AstroMind -- Day 3 Knowledge Layer Test")
    print("=" * 60)

    try:
        test_similarity_search()
        test_no_duplicate_ingestion()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)

    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    main()