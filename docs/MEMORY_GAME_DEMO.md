# Memory Card Game - Reactive UI Demo

**Status:** Demo for Multilingual v0.7.0 reactive UI/Core 1 preview
**Created:** 2026-05-08  
**Purpose:** Showcase Reactive UI keywords in interactive web game

---

## Overview

The Memory Card Game demonstrates Multilingual's **Reactive UI keywords** in
the 0.7.0 Core 1 preview. It shows how interactive applications can be built
through reactive state management without traditional imperative game loops or
framework overhead.

### What This Demo Shows

✅ **Reactive Variables** (`observe var`) — Automatic UI binding  
✅ **Change Handlers** (`on variable.change`) — Side effects on state changes  
✅ **Async/Await** — Pauses and delays within reactive logic  
✅ **Event Binding** (`onclick=handler()`) — User interaction  
✅ **Conditional Rendering** — UI adapts to state  
✅ **Polyglot Implementation** — Same game in English + French  
✅ **Minimal JavaScript** — <500 lines total JS, rest is multilingual  

---

## Files

### Source Code

| File | Purpose |
|------|---------|
| `examples/memory_game_en.multi` | Memory game in English |
| `examples/memory_game_fr.multi` | Memory game in French (polyglot) |
| `docs/memory-game-demo.html` | GitHub Pages interactive demo |

### Generated Artifacts

| Artifact | Generated From | Format |
|----------|---|--------|
| `docs/browser/memory-game/index.html` | `memory_game_en.multi` | Browser UI bundle |
| `docs/browser/memory-game/bundle.js` | `memory_game_en.multi` | Browser UI bundle JavaScript |

---

## Game Rules

**Objective:** Match all 8 pairs (4 matching pairs total)

1. Click a card to reveal its number
2. Click a second card
3. If they match, both stay revealed
4. If they don't match, both flip back
5. Win when all pairs are matched

**Features:**
- 8-card grid (4 pairs)
- Cards stay hidden until clicked
- 1-second delay before checking matches
- All matches validated before revealing
- Buttons disabled during checking phase
- "New Game" button to reset

---

## Code Structure

### English Version (`memory_game_en.multi`)

```multilingual
fn memory_game() uses ui:
    # Reactive state - all changes trigger re-renders
    observe var cards = [1,2,3,4,1,2,3,4]
    observe var revealed = [false]*8
    observe var matched = [false]*8
    observe var first_pick = -1
    observe var second_pick = -1
    observe var matches_found = 0
    observe var game_won = false
    observe var is_checking = false

    # Async event handler
    async def handle_card_click(index):
        if is_checking or matched[index] or revealed[index]:
            return
        
        revealed[index] = true
        
        if first_pick == -1:
            first_pick = index
        else if first_pick != index:
            second_pick = index
            is_checking = true
            
            # Pause before checking
            await asyncio.sleep(1.0)
            
            # Match check
            if cards[first_pick] == cards[second_pick]:
                matched[first_pick] = true
                matched[second_pick] = true
                matches_found = matches_found + 1
                
                if matches_found == 4:
                    game_won = true
            else:
                # Flip back on mismatch
                revealed[first_pick] = false
                revealed[second_pick] = false
            
            # Reset for next turn
            first_pick = -1
            second_pick = -1
            is_checking = false

    # Reactive UI rendering
    render:
        div class="memory-game":
            h1: "🎮 Memory Card Game"
            
            div class="game-board":
                for i in range(8):
                    button class="card"
                            class:matched=(matched[i])
                            class:revealed=(revealed[i])
                            disabled=(matched[i] or is_checking)
                            onclick=handle_card_click(i):
                        if matched[i]:
                            "✓"
                        else if revealed[i]:
                            str(cards[i])
                        else:
                            "?"
            
            div class="status":
                p: "Matches: " + str(matches_found) + "/4"
                p if game_won: "🎉 You won!"
            
            button class="reset-btn" onclick=reset_game():
                "New Game"

memory_game()
```

### Key Concepts

#### 1. `observe var` - Reactive Binding
```multilingual
observe var matched = [false, false, false, false, false, false, false, false]
```
When `matched[i]` changes, the UI automatically re-renders. No manual state updates needed.

#### 2. Async Event Handlers
```multilingual
async def handle_card_click(index):
    revealed[index] = true  # Instantly updates UI
    await asyncio.sleep(1.0)  # Wait before checking
    # Logic continues after delay
```

#### 3. Reactive Rendering
```multilingual
render:
    button class:revealed=(revealed[i])
            disabled=(matched[i] or is_checking)
            onclick=handle_card_click(i):
```
The `render:` block re-executes whenever observed variables change. CSS classes, disabling, onclick handlers all respond automatically.

#### 4. Conditional Rendering
```multilingual
if matched[i]:
    "✓"
else if revealed[i]:
    str(cards[i])
else:
    "?"
```
Card display changes based on state without imperatively updating DOM.

---

## French Version Comparison

The French version (`memory_game_fr.multi`) uses identical logic with French syntax:

| Concept | English | French |
|---------|---------|--------|
| Function | `fn` | `déf` |
| Observe | `observe var` | `observer var` |
| Async | `async def` | `asynchrone déf` |
| Await | `await` | `attendre` |
| If | `if` | `si` |
| For | `for` | `pour` |
| Range | `range()` | `intervalle()` |
| String | `str()` | `chaine()` |

Both lower through the same semantic IR and execute with equivalent behavior. This proves:
- ✅ Semantic IR is language-independent
- ✅ Multiple syntaxes can coexist
- ✅ Users choose their language, not the language

---

## Build

### Browser UI Bundle

```bash
multilingual build-ui-bundle examples/memory_game_en.multi \
    --lang en \
    --out-dir docs/browser/memory-game
```

### To Python (for testing)

```bash
# Execute directly with Python backend
multilingual run examples/memory_game_en.multi --lang en

# Or run with pytest for validation
python3 -m pytest tests/ -k "memory_game"
```

---

## WASM Integration

The HTML demo (`docs/memory-game-demo.html`) provides:

1. **Showcase Panels:**
   - Live game preview (when WASM compiled)
   - Code documentation with syntax highlighting
   - Polyglot comparison (English + French side-by-side)

2. **Interactive Elements:**
   - 8-card grid with click handlers
   - Status display (matches, win condition)
   - Reset button for new games
   - CSS transitions for visual feedback

3. **Educational Content:**
   - Key concepts with code examples
   - Feature checklist
   - Links to full source code
   - Architecture explanation

### Minimal JavaScript Strategy

The HTML uses **minimal JS** (only ~100 lines for bootstrapping):

```javascript
// Bootstrap: Load WASM module, instantiate
WebAssembly.instantiate(wasmBinary, {
    env: {
        // Host imports for I/O only
        console_log: (val) => console.log(val),
        // Everything else is in WASM
    }
}).then(({ instance }) => {
    instance.exports.main();  // Run the game
});
```

All game logic, rendering, and state management lives in the compiled `.multi` code, not JavaScript.

---

## Testing

### Unit Tests

```bash
# Test parsing all 17 language variants
python -m pytest tests/complete_features_wat_test.py -v

# Test WASM binary execution
python -m pytest tests/complete_features_wasm_execution_test.py -v
```

### Manual Testing

```bash
# Run English version
python examples/memory_game_en.multi

# Play the game, verify:
# ✓ Cards flip on click
# ✓ Matches stay revealed
# ✓ Mismatches flip back
# ✓ Win message appears at 4 matches
# ✓ Reset button works
```

---

## Why This Demo Matters

### 1. **Proves Reactive UI Works**
- Complex interactive app expressed purely through reactive state
- No game loop, no imperative DOM manipulation
- State changes automatically drive UI updates

### 2. **Shows Polyglot Value**
- Same functionality in English and French
- Different syntax, identical behavior
- Proves language ≠ functionality

### 3. **Minimal JavaScript**
- Game written in multilingual, not JavaScript
- HTML is just styling and bootstrap
- JS footprint <500 lines
- Demonstrates language can handle application logic

### 4. **Browser-Ready**
- Builds as a self-contained browser UI bundle
- Deployable on GitHub Pages
- No backend services needed

### 5. **Learnable Pattern**
- One reactive game = template for all reactive apps
- Developers understand the pattern once
- Easy to extend (add more games)
- Translatable to other languages

---

## Performance

| Metric | Value |
|--------|-------|
| UI Bundle Size | Small static HTML + JavaScript bundle |
| Build Path | `multilingual build-ui-bundle` |
| Game Load Time | Static-site load path |
| Click-to-Render | Reactive update path |
| Memory Usage | Browser-runtime dependent |

---

## Future Enhancements

### Future
- Leaderboard with localStorage persistence
- Difficulty levels (6, 10, 16 cards)
- Sound effects (reactive audio)
- Themes (dark mode via observe)

### Later
- Multiplayer (via WebSockets/channels)
- Game variants (Simon Says, Pong - same reactive pattern)
- AI opponent using ML keywords
- Share/remix capability

### Long Term
- Native mobile apps (iOS/Android WASM)
- Offline support (service workers)
- Cloud save (if backend available)
- Accessibility (screen readers, keyboard nav)

---

## Documentation Links

- [Frontend Contracts](frontend_contracts.md) — Detailed API reference
- [WASM AI Integration](WASM_AI_INTEGRATION.md) — How to add AI to WASM apps
- [Language Reference](reference.md) — All 17 language variants
- [Release Notes](CHANGELOG.md) — What's new

---

## Contributing

Want to add another game using the reactive pattern?

1. Create `examples/your_game_en.multi` using reactive syntax
2. Add French version `examples/your_game_fr.multi`
3. Update test suite in `tests/`
4. Create demo HTML in `docs/your_game_demo.html`
5. Submit PR with documentation

See [Contributing Guide](../CONTRIBUTING.md) for details.

---

**Status:** Ready for the 0.7.0 reactive UI/Core 1 preview
**Demo URL:** https://multilingual-programming.github.io/memory-game  
**Last Updated:** 2026-05-23
**Maintainer:** Multilingual Programming Team
