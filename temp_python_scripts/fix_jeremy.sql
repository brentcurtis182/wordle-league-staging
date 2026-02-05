-- Fix Jeremy's score for Wordle 1623
-- His 4/6 was overwritten by a reaction message showing 3/6

-- First, find Jeremy's player_id
SELECT id, name, phone_number FROM players 
WHERE league_id = 7 AND phone_number LIKE '%8587751124%';

-- Update scores table (permanent history)
UPDATE scores
SET score = 4, 
    emoji_pattern = '🟩🟩⬛⬛⬛
🟩🟩⬛⬛⬛
🟩🟩🟩🟩⬛
🟩🟩🟩🟩🟩',
    timestamp = NOW()
WHERE player_id = (SELECT id FROM players WHERE league_id = 7 AND phone_number LIKE '%8587751124%')
  AND wordle_number = 1623;

-- Update latest_scores table (for Latest Scores tab)
UPDATE latest_scores
SET score = 4,
    emoji_pattern = '🟩🟩⬛⬛⬛
🟩🟩⬛⬛⬛
🟩🟩🟩🟩⬛
🟩🟩🟩🟩🟩',
    timestamp = NOW()
WHERE player_id = (SELECT id FROM players WHERE league_id = 7 AND phone_number LIKE '%8587751124%')
  AND wordle_number = 1623;

-- Verify the fix
SELECT p.name, s.score, s.wordle_number, s.timestamp
FROM scores s
JOIN players p ON s.player_id = p.id
WHERE p.league_id = 7 AND s.wordle_number = 1623
ORDER BY s.score;
