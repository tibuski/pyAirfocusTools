#!/usr/bin/env python3
"""
set_field_options.py
Manage custom field options for Airfocus fields via CLI.
"""
import argparse
import sys
from utils import (
    load_config, 
    load_registries, 
    get_field_by_name, 
    get_field_options, 
    add_field_options,
    reorder_field_options,
    supports_field_options
)


def main():
    parser = argparse.ArgumentParser(
        description="Manage custom field options for Airfocus fields.",
        usage="uv run python set_field_options.py --field <FIELD_NAME> [--input <FILE>] [--reorder] [--show-ids] [--no-verify-ssl]"
    )
    parser.add_argument('--field', required=False, help='The name of the field to manage.')
    parser.add_argument('--input', help='Path to a text file containing options (one per line).')
    parser.add_argument('--reorder', action='store_true', help='Reorder existing options based on the order in --input file (requires --input).')
    parser.add_argument('--show-ids', action='store_true', help='Display option IDs alongside names.')
    parser.add_argument('--debug', action='store_true', help='Show debug information including API request data.')
    parser.add_argument('--no-verify-ssl', action='store_true', help='Ignore SSL certificate verification errors.')
    args = parser.parse_args()

    # Display help if no field provided
    if not args.field:
        parser.print_help()
        sys.exit(1)
    
    # Validate argument combinations
    if args.reorder and not args.input:
        print("Error: --reorder requires --input to specify the desired order.")
        sys.exit(1)

    # Load configuration and registries
    config = load_config()
    load_registries(verify_ssl=not args.no_verify_ssl)
    
    field_name = args.field
    verify_ssl = not args.no_verify_ssl
    
    # Retrieve full field configuration
    field = get_field_by_name(field_name, verify_ssl=verify_ssl)
    
    if not field:
        print(f"Error: Field '{field_name}' not found.")
        sys.exit(1)
    
    field_id = field.get('id')
    field_type_id = field.get('typeId')
    
    # Check if field type supports options
    if not supports_field_options(field_type_id):
        print(f"Error: Field '{field_name}' (type: {field_type_id}) does not support options.")
        print(f"Only select/dropdown fields support option management.")
        sys.exit(1)
    
    # Generate output filename (remove spaces from field name)
    out_file = f"field_{field_name.replace(' ', '')}_options.txt"
    
    # Fetch current options (get full objects if showing IDs)
    if args.show_ids:
        current_option_objects = get_field_options(field_id, verify_ssl=verify_ssl, full_objects=True)
        current_options = [opt.get('name', '') for opt in current_option_objects]
    else:
        current_options = get_field_options(field_id, verify_ssl=verify_ssl, full_objects=False)
        current_option_objects = None
    
    # Display options to console
    print(f"\nCurrent options for field '{field_name}' ({len(current_options)} total):")
    if current_options:
        if args.show_ids and current_option_objects:
            for i, opt_obj in enumerate(current_option_objects, 1):
                opt_name = opt_obj.get('name', '')
                opt_id = opt_obj.get('id', 'N/A')
                print(f"  {i}. {opt_name} [ID: {opt_id}]")
        else:
            for i, opt in enumerate(current_options, 1):
                print(f"  {i}. {opt}")
    else:
        print("  (No options defined)")
    
    # Save to file (always save just names for easy editing)
    with open(out_file, 'w', encoding='utf-8') as f:
        for opt in current_options:
            f.write(f"{opt}\n")
    
    print(f"\nSaved {len(current_options)} existing options to '{out_file}'.")
    
    # If input file provided, process it
    if args.input:
        # Read options from input file
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                input_opts_list = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"\nError: Input file '{args.input}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"\nError reading input file: {e}")
            sys.exit(1)
        
        if args.reorder:
            # Reorder mode: reorder existing options based on input file order
            print(f"\n--- REORDER MODE ---")
            print(f"Will reorder options based on the order in '{args.input}'")
            
            # Show the new order
            current_set = set(current_options)
            found_in_input = [opt for opt in input_opts_list if opt in current_set]
            not_found = [opt for opt in input_opts_list if opt not in current_set]
            not_in_input = [opt for opt in current_options if opt not in input_opts_list]
            
            print(f"\nNew order ({len(found_in_input)} options):")
            for i, opt in enumerate(found_in_input, 1):
                print(f"  {i}. {opt}")
            
            if not_in_input:
                print(f"\nOptions not in input file will be appended at the end ({len(not_in_input)} options):")
                for opt in not_in_input:
                    print(f"  - {opt}")
            
            if not_found:
                print(f"\nWarning: The following options from input file do not exist and will be ignored:")
                for opt in not_found:
                    print(f"  - {opt}")
            
            # Confirmation prompt
            confirm = input("\nProceed with reordering? (y/n): ").strip().lower()
            
            if confirm != 'y':
                print("Aborted by user.")
                sys.exit(0)
            
            # Reorder options
            try:
                if args.debug:
                    print("\n[DEBUG] Attempting to reorder options...")
                    print(f"[DEBUG] Field ID: {field_id}")
                    print(f"[DEBUG] Number of options to reorder: {len(found_in_input)}")
                reordered, unchanged = reorder_field_options(field_id, input_opts_list, verify_ssl=verify_ssl)
                print(f"\nSuccessfully reordered field '{field_name}'.")
                print(f"  - {reordered} options positioned as specified")
                print(f"  - {unchanged} options kept at the end")
            except Exception as e:
                print(f"\nError reordering options: {e}")
                if args.debug:
                    import traceback
                    traceback.print_exc()
                sys.exit(1)
        else:
            # Add mode: add new options from input file
            input_opts_set = set(input_opts_list)
            to_add = input_opts_set - set(current_options)
            
            if to_add:
                print(f"\n--- ADD MODE ---")
                print(f"The following {len(to_add)} new option(s) will be added to field '{field_name}':")
                for opt in input_opts_list:  # Preserve order from input file
                    if opt in to_add:
                        print(f"  - {opt}")
                
                # Confirmation prompt
                confirm = input("\nProceed with adding these options? (y/n): ").strip().lower()
                
                if confirm != 'y':
                    print("Aborted by user.")
                    sys.exit(0)
                
                # Add new options (preserve order from input file)
                to_add_ordered = [opt for opt in input_opts_list if opt in to_add]
                try:
                    add_field_options(field_id, to_add_ordered, verify_ssl=verify_ssl)
                    print(f"\nSuccessfully added {len(to_add)} new option(s) to field '{field_name}'.")
                except Exception as e:
                    print(f"\nError adding options: {e}")
                    sys.exit(1)
            else:
                print(f"\nNo new options to add. All options from '{args.input}' already exist in field '{field_name}'.")
    
    print("\nDone.")


if __name__ == "__main__":
    main()
