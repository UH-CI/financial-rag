from step1_get_context import fetch_documents
from step2_reorder_context import reorder_documents
from step3_retrieve_docs import retrieve_documents
from step4_get_numbers import extract_number_context
from step5_fiscal_note_gen import generate_fiscal_notes


# Initialize variables
saved_path = None
chronological_path = None
documents_path = None

extract_number_context("./SB_526_2025/documents", "./SB_526_2025/SB_526_2025_numbers.json")

# try:
#     saved_path = fetch_documents("https://www.capitol.hawaii.gov/session/measure_indiv.aspx?billtype=HB&billnumber=727&year=2025")
#     print(f"successfully fetched documents")
#     print(saved_path)
# except Exception as e:
#     print(f"error fetching documents: {e}")


# if saved_path:
#     try:
#         chronological_path = reorder_documents(saved_path)
#         print(f"successfully reordered documents")
#         print(chronological_path)
#     except Exception as e:
#         print(f"error reordering documents: {e}")

# if chronological_path:
#     try:
#         documents_path = retrieve_documents(chronological_path)
#         print(f"successfully retrieved documents")
#         print(documents_path)
#     except Exception as e:
#         print(f"error retrieving documents: {e}")

# documents_path = "./HB_727_2025/documents"
# try:
#     fiscal_notes_path = generate_fiscal_notes(documents_path)
#     print(f"successfully generated fiscal notes")
#     print(fiscal_notes_path)
# except Exception as e:
#     print(f"error generating fiscal notes: {e}")