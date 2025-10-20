/**
 * Cost calculation utilities for GPT-4o mini token usage
 * 
 * Pricing (as of 2024):
 * - Input tokens: $0.150 per 1M tokens ($0.00000015 per token)
 * - Output tokens: $0.600 per 1M tokens ($0.00000060 per token)
 */

// Pricing constants (per token)
const INPUT_TOKEN_COST = 0.00000015;  // $0.150 per 1M tokens
const OUTPUT_TOKEN_COST = 0.00000060; // $0.600 per 1M tokens

/**
 * Calculate the cost for a given number of input and output tokens
 */
export function calculateCost(inputTokens: number, outputTokens: number): number {
  return (inputTokens * INPUT_TOKEN_COST) + (outputTokens * OUTPUT_TOKEN_COST);
}

/**
 * Format a cost value as a USD currency string
 */
export function formatCost(cost: number): string {
  return `$${cost.toFixed(6)}`;
}

/**
 * Calculate the total cost for all operations
 */
export function calculateTotalCost(
  summarizationInput: number,
  summarizationOutput: number,
  taggingInput: number,
  taggingOutput: number
): number {
  const summarizationCost = calculateCost(summarizationInput, summarizationOutput);
  const taggingCost = calculateCost(taggingInput, taggingOutput);
  return summarizationCost + taggingCost;
}

/**
 * Get a breakdown of costs by operation
 */
export interface CostBreakdown {
  summarizationCost: number;
  taggingCost: number;
  totalCost: number;
}

export function getCostBreakdown(
  summarizationInput: number,
  summarizationOutput: number,
  taggingInput: number,
  taggingOutput: number
): CostBreakdown {
  const summarizationCost = calculateCost(summarizationInput, summarizationOutput);
  const taggingCost = calculateCost(taggingInput, taggingOutput);
  
  return {
    summarizationCost,
    taggingCost,
    totalCost: summarizationCost + taggingCost,
  };
}

