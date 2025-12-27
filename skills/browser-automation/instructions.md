# Browser Automation Instructions (Tier 2)

Use Puppeteer MCP when WebFetch isn't enough.

## When to Use

| Scenario | Use |
|----------|-----|
| Static HTML content | WebFetch |
| JS-rendered content (React, Vue) | Puppeteer |
| Need screenshots | Puppeteer |
| Form interaction | Puppeteer |
| Auth-protected pages | Puppeteer |

## Core Tools

```
puppeteer_navigate   - Go to URL
puppeteer_screenshot - Capture page/element
puppeteer_click      - Click element by selector
puppeteer_fill       - Fill input field
puppeteer_select     - Select dropdown option
puppeteer_hover      - Hover over element
puppeteer_evaluate   - Run JavaScript in page
```

## Workflow Pattern

1. **Navigate** to the page
2. **Screenshot** initial state (for debugging)
3. **Wait** for elements to load
4. **Interact** (click, fill, etc.)
5. **Screenshot** result
6. **Extract** data if needed
7. **Close** when done

## Best Practices

- Screenshot before AND after actions
- Use specific selectors (ID > class > tag)
- Add waits for dynamic content
- Handle errors gracefully (element not found)
- Close browser session when finished

## Should NOT Do

- Use for simple static pages (WebFetch is faster)
- Leave browser sessions open
- Click without waiting for element
- Ignore screenshot evidence

## Common Selectors

```css
#id              /* By ID */
.class           /* By class */
button[type=submit]  /* By attribute */
form input:first    /* Pseudo-selectors */
```

## Escalate When

- Site blocks automation (CAPTCHA)
- Complex auth flows (OAuth, MFA)
- Heavy JS frameworks timing out
- Need persistent session state

For advanced patterns, see SKILL.md.
