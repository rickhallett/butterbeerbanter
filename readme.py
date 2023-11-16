# First, let's filter out only the major headings and subheadings (i.e., #, ##, ###) from the readme content.
import re

major_headings = {}
current_heading = None
current_subheading = None

# Regular expressions for different levels of headings
heading_patterns = {
    1: re.compile(r'^#\s+(.*)\s*$'),
    2: re.compile(r'^##\s+(.*)\s*$'),
    3: re.compile(r'^###\s+(.*)\s*$')
}

for line in readme_content:
    for level, pattern in heading_patterns.items():
        match = pattern.match(line)
        if match:
            heading = match.group(1).strip()
            if level == 1:
                current_heading = heading
                major_headings[current_heading] = {'subheadings': {}}
            elif level == 2 and current_heading:
                current_subheading = heading
                major_headings[current_heading]['subheadings'][current_subheading] = []
            elif level == 3 and current_heading and current_subheading:
                major_headings[current_heading]['subheadings'][current_subheading].append(heading)

major_headings
