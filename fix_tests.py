import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Revert earlier incorrect fixes to proposed_*
    content = content.replace("gen_result = compose_atomic_claims_llm", "proposed_ = compose_atomic_claims_llm")
    
    # Just fix compose_atomic_claims_llm calls to append ['claims']
    # Example: proposed_openai = compose_atomic_claims_llm(...)
    
    # Simple replace
    new_content = re.sub(
        r'(proposed_[a-zA-Z0-9_]*) = compose_atomic_claims_llm\((.*?)\)',
        r'\1 = compose_atomic_claims_llm(\2)["claims"]',
        content
    )
    
    # Also fix proposed = compose_atomic_claims_llm
    new_content = re.sub(
        r'proposed = compose_atomic_claims_llm\((.*?)\)',
        r'proposed = compose_atomic_claims_llm(\1)["claims"]',
        new_content
    )
    
    # Revert tests doing proposed_null["claims"]
    new_content = new_content.replace('proposed_null["claims"]', 'proposed_null')
    new_content = new_content.replace('proposed_openai["claims"]', 'proposed_openai')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

for root, _, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))
print('Tests updated via script')
