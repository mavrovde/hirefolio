import os

test_dir = 'backend/tests'
for root, _, files in os.walk(test_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if skip_next:
                    if line.strip().endswith(')'):
                        skip_next = False
                    continue
                
                if '@pytest.mark.xfail' in line:
                    if not line.strip().endswith(')'):
                        skip_next = True
                    continue
                    
                new_lines.append(line)
                
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
print("done")
