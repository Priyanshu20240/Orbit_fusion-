import base64

icons = {
    'RECT': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#3b82f6"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>',
    'POLY': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#10b981"><path d="M12 2L2 9L6 21H18L22 9L12 2Z"/></svg>',
    'EDIT': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" fill="#fbbf24" stroke="none"/></svg>',
    'DEL': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#ef4444"><path d="M20 6H4V18C4 19.1046 4.89543 20 6 20H18C19.1046 20 20 19.1046 20 18V6Z"/><path d="M9 6V4C9 2.89543 9.89543 2 11 2H13C14.1046 2 15 2.89543 15 4V6" fill="none" stroke="#ef4444" stroke-width="2"/></svg>'
}

with open('icons.txt', 'w') as f:
    for name, svg in icons.items():
        b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
        f.write(f"{name}: data:image/svg+xml;base64,{b64}\n")
