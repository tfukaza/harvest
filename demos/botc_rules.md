# Blood on the Clocktower — Trouble Brewing (7 Players)

## Overview

Blood on the Clocktower is a social deduction game. A town of players must
figure out who among them is the Demon before the Demon kills them all. Each
player has a secret role with a unique ability. The Storyteller (moderator)
runs the game, manages night actions, and delivers information.

There are two teams: **Good** (Townsfolk + Outsiders) and **Evil** (Demon +
Minions). Good players don't know each other's roles. Evil players know each
other from the start.

## Teams

- **Good (5 players):** 4 Townsfolk + 1 Outsider. Goal: execute the Demon.
- **Evil (2 players):** 1 Demon + 1 Minion. Goal: reduce the town to 2 alive
  players (the Demon + 1 other).

## Roles

### Townsfolk (Good — 4 players)

| Role | Night Ability |
|---|---|
| **Washerwoman** | On Night 0 only: learns that one of two players is a specific Townsfolk role. Example: "Either Alice or Bob is the Empath." |
| **Empath** | Each night: learns how many of their two alive neighbours (in seating order) are Evil. Returns 0, 1, or 2. |
| **Investigator** | On Night 0 only: learns that one of two players is a specific Minion role. Example: "Either Charlie or Dana is the Poisoner." |
| **Chef** | On Night 0 only: learns the number of pairs of Evil players sitting next to each other in seating order. Returns 0 or 1 (with 2 evil players, max is 1). |

### Outsider (Good — 1 player)

| Role | Effect |
|---|---|
| **Drunk** | Thinks they are a Townsfolk (the Storyteller tells them a fake Townsfolk role). Their ability malfunctions — any information they receive may be false. The Drunk does NOT know they are the Drunk. |

### Minion (Evil — 1 player)

| Role | Night Ability |
|---|---|
| **Poisoner** | Each night: chooses a player to poison. That player's ability malfunctions until the next night (they may receive false information). |

### Demon (Evil — 1 player)

| Role | Night Ability |
|---|---|
| **Imp** | Each night (starting Night 1): kills one player. That player dies and is announced at the start of the next day. |

## Game Flow

### Night 0 (Setup Night)
1. Storyteller assigns roles to all players.
2. Evil players (Imp + Poisoner) learn each other's identities via a private channel.
3. Poisoner chooses their first poison target.
4. Storyteller resolves Night 0 information abilities (Washerwoman, Investigator, Chef, Empath) and DMs results to each player. The Drunk receives false info for their fake role. Poisoned players receive false info.

### Day Phase
1. Storyteller announces who died overnight (if anyone).
2. All alive players discuss in the town square. Players share (or lie about) their information, accuse others, and form theories.
3. **Nominations:** Any alive player may nominate another alive player for execution. The Storyteller calls for a vote.
4. **Voting:** All alive players vote (publicly in town square — thumbs up or down). Dead players get exactly one vote for the rest of the game. A nomination passes if it receives votes from more than half of the alive players AND more votes than any previous nomination that day.
5. **Execution:** At the end of the day, the player with the most passing votes (if any) is executed and dies. The Storyteller announces their alignment (Good or Evil) but NOT their specific role.
6. If the Demon dies from execution, **Good wins immediately**.

### Night Phase (Night 1+)
1. Poisoner chooses a new poison target (or keeps the same one).
2. Imp chooses a player to kill.
3. Empath receives their nightly info.
4. Storyteller resolves all abilities and prepares for the next day.

### Repeat until a win condition is met.

## Win Conditions

- **Good wins:** The Demon (Imp) is executed during the day.
- **Evil wins:** Only 2 players remain alive (which must include the Demon).

## Seating Order

Players are arranged in a circle. The seating order matters for the Empath
(checks alive neighbours) and the Chef (checks adjacent Evil pairs). The
Storyteller announces the seating order at game start.

## Key Strategy Notes

**For Good players:**
- Share your information, but be cautious — the Poisoner can make your info wrong.
- Cross-reference claims. If two players' information contradicts, one may be evil or poisoned.
- The Drunk's info is always unreliable, but they don't know they're the Drunk.
- Nominate and vote strategically — you need to find the Demon before the town is too small.

**For Evil players:**
- You know each other. Coordinate privately.
- The Poisoner should poison info roles (Empath, Washerwoman, Investigator) to create confusion.
- Blend in. Claim to be a Townsfolk role and fabricate plausible information.
- Avoid both being nominated on the same day — losing both evil players ends the game.

## Communication Rules

- **Town Square:** Public channel for all alive players. All discussion, nominations, and voting happen here.
- **DMs with Storyteller:** Private. The Storyteller delivers night information and collects night actions (Imp kill target, Poisoner poison target) via DM.
- **Evil Team Channel:** Private channel for Imp + Poisoner to coordinate. Created by Storyteller at game start.
- **Player-Created Channels:** Players may create private channels for alliance discussions. Other players cannot see these channels.
- **Dead players** can still talk in Town Square but have limited influence (only 1 remaining vote total).
