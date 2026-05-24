#include <stdlib.h>
#include <float.h>
#include <math.h>

#if defined(_WIN32)
    #define EXPORT __declspec(dllexport)
#else
    #define EXPORT
#endif

/**
 * Algoritmo di DTW 2D
 * 
 * @param pointsA matrice leneare di punti [n x 2]
 * @param pointsB matrice leneare di punti [m x 2]
 * @param countA  quantità di punti presenti in pointsA
 * @param countB  quantità di punti presenti in pointsB
 * 
 * @return costo finale del DTW
 */
EXPORT double DtwCost2D(const double* pointsA, int countA, const double* pointsB, int countB, double bestCost)
{
    // Alloca la matrice lineare dei cost
    double* costMatrix = (double*)malloc((countA + 1) * (countB + 1) * sizeof(double));

    // Inizializza tutta la matrice ad infinito
    for (int i = 0; i <= countA; i++)
    {
        for (int j = 0; j <= countB; j++)
        {
            costMatrix[i * (countB + 1) + j] = INFINITY;
        }
    }

    costMatrix[0] = 0.0;

    // Algoritmo di DTW
    for (int i = 1; i <= countA; i++)
    {
        double rowMin = INFINITY;

        for (int j = 1; j <= countB; j++)
        {
            double deltaX = pointsA[(i - 1) * 2]     - pointsB[(j - 1) * 2];
            double deltaY = pointsA[(i - 1) * 2 + 1] - pointsB[(j - 1) * 2 + 1];
            double distance = sqrt(deltaX * deltaX + deltaY * deltaY);

            double insertion = costMatrix[(i - 1) * (countB + 1) + j];
            double deletion  = costMatrix[i       * (countB + 1) + (j - 1)];
            double match     = costMatrix[(i - 1) * (countB + 1) + (j - 1)];

            double minPrev = insertion < deletion ? insertion : deletion;
            minPrev = minPrev < match ? minPrev : match;

            double cell = distance + minPrev;
            costMatrix[i * (countB + 1) + j] = cell;

            if (cell < rowMin)
                rowMin = cell;
        }

        // Early return valido: rowMin è un lower bound del costo finale.
        // Se anche il valore più basso della riga supera bestCost,
        // nessun percorso che attraversa questa riga può migliorare bestCost.
        if (rowMin >= bestCost)
        {
            free(costMatrix);
            return rowMin;
        }
    }

    // Reperisce il costo finale
    double result = costMatrix[countA * (countB + 1) + countB];
    free(costMatrix);

    return result;
}