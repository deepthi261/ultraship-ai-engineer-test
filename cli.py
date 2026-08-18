"""
CLI Runner for UltraShip Document Extraction Pipeline.
"""

import sys
import os
import json
import argparse
from src.pipeline import ExtractionPipeline


def main():
    parser = argparse.ArgumentParser(description="UltraShip Freight Rate Confirmation Extraction Pipeline")
    parser.add_argument("--file", "-f", type=str, help="Path to raw rate confirmation text file")
    parser.add_argument("--sample", "-s", type=int, choices=[1, 2, 3], help="Run pipeline on sample rate con (1, 2, or 3)")
    parser.add_argument("--all", "-a", action="store_true", help="Run pipeline on all 3 sample rate confirmations")
    parser.add_argument("--provider", "-p", type=str, default="auto", choices=["auto", "gemini", "openai", "mock"], help="LLM provider to use")
    parser.add_argument("--show-audit", action="store_true", help="Display internal audit warnings alongside extracted JSON")

    args = parser.parse_args()

    pipeline = ExtractionPipeline(provider_name=args.provider)

    samples_dir = os.path.join(os.path.dirname(__file__), "samples")

    files_to_process = []

    if args.file:
        files_to_process.append(args.file)
    elif args.sample:
        files_to_process.append(os.path.join(samples_dir, f"rate_con_sample_{args.sample}.txt"))
    elif args.all:
        files_to_process = [
            os.path.join(samples_dir, f"rate_con_sample_{i}.txt")
            for i in range(1, 4)
        ]
    else:
        print("No input file specified. Defaulting to running all samples (--all).\n")
        files_to_process = [
            os.path.join(samples_dir, f"rate_con_sample_{i}.txt")
            for i in range(1, 4)
        ]

    for file_path in files_to_process:
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            continue

        print("=" * 80)
        print(f" PROCESSING FILE: {os.path.basename(file_path)}")
        print("=" * 80)

        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        rate_con = pipeline.process_text(raw_text)
        clean_json = rate_con.to_clean_dict()

        print(json.dumps(clean_json, indent=2))
        
        if args.show_audit or True:  # Print audit summary
            print("\n--- Pipeline Internal Audit ---")
            print(f"Confidence Level: {rate_con.confidence.upper()}")
            if rate_con.validation_warnings:
                print("Validation Warnings / Adjustments:")
                for w in rate_con.validation_warnings:
                    print(f"  • {w}")
            else:
                print("Validation Warnings: None (Clean Extraction)")
        print("\n")


if __name__ == "__main__":
    main()
