#!/usr/bin/env python3
"""
Interactive script to find semantically similar bills using TF-IDF and Gemini embeddings.
Allows user to input a bill name and get ranked similarity results.
"""

import json
import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple, Dict
import argparse

class BillSimilaritySearcher:
    def __init__(self, vectors_file: str):
        self.vectors_file = vectors_file
        self.data = None
        self.documents = None
        self.tfidf_vectors = None
        self.embeddings = None
        self.bill_name_to_index = {}
        
    def load_data(self) -> None:
        """Load the processed vectors and embeddings."""
        print(f"Loading data from {self.vectors_file}...")
        
        if not os.path.exists(self.vectors_file):
            print(f"Error: Vector file {self.vectors_file} not found!")
            print("Please run compute_tfidf_embeddings.py first to generate the vectors.")
            return
        
        with open(self.vectors_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.documents = self.data['documents']
        
        # Convert vectors back to numpy arrays
        self.tfidf_vectors = np.array([doc['tfidf_vector'] for doc in self.documents])
        self.embeddings = np.array([doc['gemini_embedding'] for doc in self.documents])
        
        # Create bill name to index mapping for quick lookup
        for i, doc in enumerate(self.documents):
            self.bill_name_to_index[doc['bill_name'].upper()] = i
        
        print(f"Loaded {len(self.documents)} documents")
        print(f"TF-IDF vectors shape: {self.tfidf_vectors.shape}")
        print(f"Embeddings shape: {self.embeddings.shape}")
    
    def find_bill_index(self, bill_name: str) -> int:
        """Find the index of a bill by name (case-insensitive)."""
        bill_name_upper = bill_name.upper()
        # Direct match
        if bill_name_upper in self.bill_name_to_index:
            return self.bill_name_to_index[bill_name_upper]
        
        # Partial match - find bills containing the search term
        matches = []
        for name, idx in self.bill_name_to_index.items():
            if bill_name_upper in name:
                matches.append((name, idx))
        
        if len(matches) == 1:
            return matches[0][1]
        elif len(matches) > 1:
            print(f"Multiple matches found for '{bill_name}':")
            for i, (name, idx) in enumerate(matches[:10]):  # Show first 10 matches
                print(f"  {i+1}. {name}")
            
            try:
                choice = int(input("Enter the number of your choice: ")) - 1
                if 0 <= choice < len(matches):
                    return matches[choice][1]
                else:
                    print("Invalid choice.")
                    return -1
            except ValueError:
                print("Invalid input.")
                return -1
        else:
            print(f"No bill found matching '{bill_name}'")
            return -1
    
    def compute_tfidf_similarity(self, query_idx: int, top_k: int = 10) -> List[Tuple[int, float]]:
        """Compute TF-IDF cosine similarity for a query document."""
        query_vector = self.tfidf_vectors[query_idx].reshape(1, -1)
        similarities = cosine_similarity(query_vector, self.tfidf_vectors)[0]
        
        # Get top-k most similar documents (excluding the query document itself)
        similar_indices = np.argsort(similarities)[::-1]
        results = []
        
        for idx in similar_indices:
            if idx != query_idx:  # Exclude self
                results.append((int(idx), float(similarities[idx])))
                if len(results) >= top_k:
                    break
        
        return results
    
    def compute_embedding_similarity(self, query_idx: int, top_k: int = 10) -> List[Tuple[int, float]]:
        """Compute embedding cosine similarity for a query document."""
        query_embedding = self.embeddings[query_idx].reshape(1, -1)
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Get top-k most similar documents (excluding the query document itself)
        similar_indices = np.argsort(similarities)[::-1]
        results = []
        
        for idx in similar_indices:
            if idx != query_idx:  # Exclude self
                results.append((int(idx), float(similarities[idx])))
                if len(results) >= top_k:
                    break
        
        return results
    
    def display_results(self, query_idx: int, tfidf_results: List[Tuple[int, float]], 
                       embedding_results: List[Tuple[int, float]]) -> None:
        """Display similarity search results."""
        query_doc = self.documents[query_idx]
        
        print(f"\n" + "="*80)
        print(f"SIMILARITY SEARCH RESULTS FOR: {query_doc['bill_name']}")
        print(f"="*80)
        print(f"Query Bill URL: {query_doc['url']}")
        print(f"Summary: {query_doc['summary'][:200]}...")
        print(f"\n" + "-"*80)
        
        # Display TF-IDF results
        print(f"\nTOP 10 SIMILAR BILLS (TF-IDF Similarity):")
        print(f"{'Rank':<4} {'Bill Name':<20} {'Similarity':<12} {'Summary Preview'}")
        print("-" * 80)
        
        for i, (idx, score) in enumerate(tfidf_results, 1):
            doc = self.documents[idx]
            summary_preview = doc['summary'][:50] + "..." if len(doc['summary']) > 50 else doc['summary']
            print(f"{i:<4} {doc['bill_name']:<20} {score:.4f}       {summary_preview}")
        
        # Display embedding results
        print(f"\nTOP 10 SIMILAR BILLS (Gemini Embedding Similarity):")
        print(f"{'Rank':<4} {'Bill Name':<20} {'Similarity':<12} {'Summary Preview'}")
        print("-" * 80)
        
        for i, (idx, score) in enumerate(embedding_results, 1):
            doc = self.documents[idx]
            summary_preview = doc['summary'][:50] + "..." if len(doc['summary']) > 50 else doc['summary']
            print(f"{i:<4} {doc['bill_name']:<20} {score:.4f}       {summary_preview}")
    
    def search_similar_bills(self, bill_name: str, top_k: int = 10) -> None:
        """Main search function."""
        tfidf_documents = []
        embedding_documents = []

        # Load data if not already loaded
        if self.data is None:
            print("Error: Data not loaded. Please run load_data() first.")
            return None, None
        
        # Find the bill
        query_idx = self.find_bill_index(bill_name)

        if query_idx == -1:
            print(f"Error: unable to find bill {bill_name}")
            return None, None
        
        print(f"\nSearching for bills similar to: {self.documents[query_idx]['bill_name']}")
        
        # Compute similarities using both methods
        tfidf_results = self.compute_tfidf_similarity(query_idx, top_k)
        embedding_results = self.compute_embedding_similarity(query_idx, top_k)
        
        # Display results
        # self.display_results(query_idx, tfidf_results, embedding_results)
        for idx, score in tfidf_results:
            tfidf_documents.append({"bill_name": self.documents[idx]['bill_name'], "summary": self.documents[idx]['summary'], "score": score})
        for idx, score in embedding_results:
            embedding_documents.append({"bill_name": self.documents[idx]['bill_name'], "summary": self.documents[idx]['summary'], "score": score})
        search_bill = {"bill_name": self.documents[query_idx]['bill_name'], "summary": self.documents[query_idx]['summary'], "score": 1.0}
        return tfidf_documents, embedding_documents, search_bill
    
    def interactive_search(self) -> None:
        """Interactive search mode."""
        print("\n" + "="*60)
        print("BILL SIMILARITY SEARCH - Interactive Mode")
        print("="*60)
        print("Enter a bill name (e.g., 'HB1001', 'HB1001_SD1_') to find similar bills.")
        print("Type 'list' to see available bills, 'quit' to exit.")
        print("-"*60)
        
        while True:
            try:
                query = input("\nEnter bill name: ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                elif query.lower() == 'list':
                    self.list_available_bills()
                elif query:
                    self.search_similar_bills(query)
                else:
                    print("Please enter a valid bill name.")
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def list_available_bills(self, limit: int = 20) -> None:
        """List available bills (first 20 by default)."""
        print(f"\nFirst {limit} available bills:")
        bill_names = list(self.bill_name_to_index.keys())[:limit]
        for i, name in enumerate(bill_names, 1):
            print(f"  {i:2d}. {name}")
        
        if len(self.bill_name_to_index) > limit:
            print(f"  ... and {len(self.bill_name_to_index) - limit} more bills")

def main():
    parser = argparse.ArgumentParser(description="Search for similar bills using TF-IDF and embeddings")
    parser.add_argument("--vectors-file", default="document_vectors.json", 
                       help="Path to the vectors JSON file")
    parser.add_argument("--bill-name", help="Bill name to search for")
    parser.add_argument("--top-k", type=int, default=10, 
                       help="Number of similar bills to return")
    
    args = parser.parse_args()
    
    # Initialize searcher
    searcher = BillSimilaritySearcher(args.vectors_file)
    searcher.load_data()
    
    if searcher.data is None:
        return
    
    # If bill name provided as argument, do single search
    if args.bill_name:
        searcher.search_similar_bills(args.bill_name, args.top_k)
    else:
        # Otherwise, start interactive mode
        searcher.interactive_search()

if __name__ == "__main__":
    main()
