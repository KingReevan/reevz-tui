def parse_input(user_input: str):
    parts = user_input.strip().split()

    if not parts:
        return None, [], {}

    command = parts[0]
    args = []
    kwargs = {}

    i = 1
    while i < len(parts):
        if parts[i].startswith("--"):
            # Handle --flag value format
            flag = parts[i][2:]
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                kwargs[flag] = parts[i + 1]
                i += 2
            else:
                kwargs[flag] = True
                i += 1
        elif parts[i].startswith("-"):
            # Handle -f value format
            flag = parts[i][1:]
            if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                kwargs[flag] = parts[i + 1]
                i += 2
            else:
                kwargs[flag] = True
                i += 1
        else:
            args.append(parts[i])
            i += 1

    return command, args, kwargs
