function randomBetween(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const mockSolvedBoard = [
  ['5', '3', '4', '6', '7', '8', '9', '1', '2'],
  ['6', '7', '2', '1', '9', '5', '3', '4', '8'],
  ['1', '9', '8', '3', '4', '2', '5', '6', '7'],
  ['8', '5', '9', '7', '6', '1', '4', '2', '3'],
  ['4', '2', '6', '8', '5', '3', '7', '9', '1'],
  ['7', '1', '3', '9', '2', '4', '8', '5', '6'],
  ['9', '6', '1', '5', '3', '7', '2', '8', '4'],
  ['2', '8', '7', '4', '1', '9', '6', '3', '5'],
  ['3', '4', '5', '2', '8', '6', '1', '7', '9'],
];

export async function mockSolveFromImage(file) {
  await wait(randomBetween(900, 1800));

  return {
    status: 'success',
    solvedBoard: mockSolvedBoard,
    meta: {
      mode: 'mock',
      filename: file.name,
      processTimeMs: randomBetween(120, 420),
      extractedClues: randomBetween(24, 34),
      confidence: Number((Math.random() * 0.08 + 0.9).toFixed(3)),
    },
  };
}

export async function mockGetStatus() {
  await wait(randomBetween(120, 280));
  const roll = Math.random();

  let serviceStatus = 'healthy';
  if (roll > 0.86 && roll <= 0.96) {
    serviceStatus = 'degraded';
  }
  if (roll > 0.96) {
    serviceStatus = 'offline';
  }

  return {
    serviceStatus,
    workerStatus: serviceStatus === 'offline' ? 'disconnected' : 'connected',
    latencyMs: randomBetween(18, 84),
    queueDepth: randomBetween(0, 3),
    timestamp: new Date().toISOString(),
    mode: 'mock',
  };
}
