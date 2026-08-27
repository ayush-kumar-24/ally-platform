/**
 * Founder quotes, grouped by the part of the day they suit.
 *
 * Grouped rather than pooled because the same line does not land at 7am and at
 * 11pm: morning is for starting, afternoon for staying with a hard thing,
 * evening for closing the loop, and night for putting it down. A founder
 * reading this at midnight does not need to be told to seize the day.
 *
 * Attributions are limited to lines that are well documented as that person's.
 * The rest are written for this product and left unattributed on purpose --
 * a made-up attribution on a real founder's dashboard is worse than no
 * attribution, and inventing one to fill the slot is exactly how that happens.
 */

export const QUOTES = {
  morning: [
    { text: 'The way to get started is to quit talking and begin doing.', by: 'Walt Disney' },
    { text: 'Make something people want.', by: 'Paul Graham' },
    { text: 'Start where you are. Use what you have. Do what you can.', by: 'Arthur Ashe' },
    { text: 'The hardest part of today is choosing what not to do.' },
    { text: 'One real conversation with a customer beats a morning of guessing.' },
  ],
  afternoon: [
    { text: 'Ideas are easy. Implementation is hard.', by: 'Guy Kawasaki' },
    { text: 'Fall in love with the problem, not the solution.', by: 'Uri Levine' },
    { text: 'The best way to predict the future is to invent it.', by: 'Alan Kay' },
    { text: 'The middle of the day is where most plans quietly get abandoned. Not today.' },
    { text: 'Slow progress on the right thing still beats fast progress on the wrong one.' },
  ],
  evening: [
    { text: "If you are not embarrassed by the first version of your product, you've launched too late.", by: 'Reid Hoffman' },
    { text: "It's not about ideas. It's about making ideas happen.", by: 'Scott Belsky' },
    { text: 'Write down what you learned today. Tomorrow you will think you already knew it.' },
    { text: 'A day where you moved one real thing forward was a good day.' },
    { text: 'Close the loop on one thing before you open another.' },
  ],
  night: [
    { text: 'Amateurs sit and wait for inspiration, the rest of us just get up and go to work.', by: 'Stephen King' },
    { text: 'The company will still be here in the morning. Rest is part of the work.' },
    { text: 'Nothing you decide at 1am is better than what you would decide at 9am.' },
    { text: 'You are allowed to stop for the day with things unfinished. They always are.' },
    { text: 'Tomorrow needs you thinking clearly more than tonight needs one more hour.' },
  ],
};
