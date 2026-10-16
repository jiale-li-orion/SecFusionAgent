type Deposit = readonly [number, number, number, number]
type Composition = {
  seed: number
  deposits: readonly [Deposit, Deposit, Deposit]
  // Drift axes, slow local migration, and convergence on interaction.
  motion: readonly [number, number, number, number]
  origin: readonly [number, number]
}

/** Art direction, never derived from counts, risk scores or task progress. */
export const developingProfiles = {
  question: {
    seed: 0,
    deposits: [[-.67, -.06, .62, .36], [.01, .06, .52, .43], [.64, -.04, .53, .30]],
    motion: [1, -1, 0, 0], origin: [-.25, .02],
  },
  // A dense, sheltered centre with an open outer edge.
  personal: {
    seed: 5.3,
    deposits: [[-.36, -.05, .66, .35], [.12, .05, .39, .42], [.50, .16, .33, .19]],
    motion: [-.35, .32, .08, .18], origin: [.12, .05],
  },
  // Two materials meeting, with a small residual deposit between them.
  welcome: {
    seed: 12.8,
    deposits: [[-.38, -.10, .68, .28], [.02, .10, .28, .22], [.40, .05, .60, .36]],
    motion: [.55, -.55, .10, .20], origin: [0, 0],
  },
  // Reading reveals overlapping strata; the shape is not a document pictogram.
  reading: {
    seed: 3.1,
    deposits: [[-.25, .20, .86, .15], [.06, .02, .70, .21], [.34, -.19, .66, .13]],
    motion: [.38, -.24, .06, .04], origin: [-.35, .16],
  },
  recommended: {
    seed: 4.7,
    deposits: [[-.65, -.10, .43, .29], [-.05, .12, .50, .36], [.63, -.08, .40, .23]],
    motion: [.75, .30, .15, .08], origin: [-.55, -.08],
  },
  following: {
    seed: 6.2,
    deposits: [[-.38, -.04, .62, .35], [.02, .04, .34, .28], [.45, .13, .45, .21]],
    motion: [-.40, -.28, .07, .18], origin: [0, 0],
  },
  hot: {
    seed: 9.4,
    deposits: [[-.45, -.15, .61, .24], [.06, .02, .40, .42], [.30, .15, .43, .25]],
    motion: [.48, .80, .11, .14], origin: [.20, .07],
  },
  events: {
    seed: 11.6,
    deposits: [[-.60, -.18, .48, .19], [-.03, 0, .50, .27], [.55, .18, .43, .20]],
    motion: [.70, .45, .09, .08], origin: [-.60, -.18],
  },
  library: {
    seed: 14.2,
    deposits: [[-.20, .20, .88, .12], [.10, -.03, .65, .16], [-.28, -.21, .71, .12]],
    motion: [.23, -.20, .04, .02], origin: [-.60, .18],
  },
  research: {
    seed: 8.2,
    deposits: [[-.62, -.18, .47, .24], [.03, .12, .39, .34], [.62, -.04, .44, .23]],
    motion: [-.65, .75, .12, .28], origin: [.03, .12],
  },
  runtime: {
    seed: 17.6,
    deposits: [[-.43, .13, .60, .22], [.03, -.10, .41, .31], [.48, .09, .58, .20]],
    motion: [.80, -.65, .12, .14], origin: [-.40, .13],
  },
  memory: {
    seed: 19.4,
    deposits: [[-.24, .17, .73, .14], [.08, -.03, .54, .24], [.25, -.21, .65, .12]],
    motion: [.25, -.20, .05, .07], origin: [.08, -.03],
  },
  observatory: {
    seed: 23.1,
    deposits: [[-.62, .15, .47, .20], [-.03, -.12, .43, .22], [.61, .09, .40, .30]],
    motion: [.42, .65, .16, .05], origin: [-.03, -.12],
  },
  world: {
    seed: 31.7,
    deposits: [[-.67, .10, .48, .29], [-.08, -.17, .54, .19], [.62, .10, .48, .32]],
    motion: [.90, .35, .15, .04], origin: [-.45, .05],
  },
} as const satisfies Record<string, Composition>

export type DevelopingVariant = keyof typeof developingProfiles
