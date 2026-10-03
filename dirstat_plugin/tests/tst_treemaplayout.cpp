#include "core/TreemapLayout.h"

#include <QTest>

#include <algorithm>
#include <cmath>

namespace
{

double area(const QRectF& r)
{
    return r.width() * r.height();
}

bool overlaps(const QRectF& a, const QRectF& b)
{
    constexpr double eps = 1e-6;
    return a.left() < b.right() - eps && b.left() < a.right() - eps && a.top() < b.bottom() - eps &&
           b.top() < a.bottom() - eps;
}

bool inside(const QRectF& inner, const QRectF& outer)
{
    constexpr double eps = 1e-6;
    return inner.left() >= outer.left() - eps && inner.top() >= outer.top() - eps &&
           inner.right() <= outer.right() + eps && inner.bottom() <= outer.bottom() + eps;
}

} // namespace

class TestTreemapLayout : public QObject
{
    Q_OBJECT

private slots:
    void rowsTileBoundsProportionally_data()
    {
        QTest::addColumn<std::vector<qint64>>("sizes");
        QTest::addColumn<QRectF>("bounds");
        QTest::newRow("single") << std::vector<qint64>{42} << QRectF(0, 0, 300, 200);
        QTest::newRow("wide") << std::vector<qint64>{6, 6, 4, 3, 2, 2, 1} << QRectF(0, 0, 6, 4);
        QTest::newRow("tall") << std::vector<qint64>{50, 20, 20, 5, 3, 1, 1}
                              << QRectF(10, 20, 80, 600);
        QTest::newRow("skewed") << std::vector<qint64>{1000000, 1, 1, 1} << QRectF(0, 0, 100, 100);
        QTest::newRow("many equal") << std::vector<qint64>(50, 7) << QRectF(0, 0, 400, 300);
    }

    void rowsTileBoundsProportionally()
    {
        QFETCH(std::vector<qint64>, sizes);
        QFETCH(QRectF, bounds);

        const std::vector<QRectF> rects = layoutRows(sizes, bounds);
        QCOMPARE(rects.size(), sizes.size());

        double total = 0;
        for (qint64 s : sizes)
        {
            total += static_cast<double>(s);
        }
        double covered = 0;
        for (std::size_t i = 0; i < rects.size(); ++i)
        {
            QVERIFY2(inside(rects[i], bounds), qPrintable(QString::number(i)));
            const double expected = area(bounds) * static_cast<double>(sizes[i]) / total;
            QVERIFY2(std::abs(area(rects[i]) - expected) < 1e-6 * area(bounds),
                     qPrintable(QStringLiteral("rect %1: %2 vs %3")
                                    .arg(i)
                                    .arg(area(rects[i]))
                                    .arg(expected)));
            covered += area(rects[i]);
            for (std::size_t j = i + 1; j < rects.size(); ++j)
            {
                QVERIFY2(!overlaps(rects[i], rects[j]), qPrintable(QStringLiteral("%1/%2").arg(i).arg(j)));
            }
        }
        QVERIFY(std::abs(covered - area(bounds)) < 1e-6 * area(bounds));
    }

    void rowsReadLargestFirstFromTopLeft()
    {
        // Wide bounds: horizontal rows, stacked downwards, each filled left to right.
        const std::vector<qint64> sizes{40, 20, 10, 8, 6, 5, 4, 3, 2, 1, 1};
        const QRectF bounds(0, 0, 400, 200);
        const std::vector<QRectF> rects = layoutRows(sizes, bounds);
        QCOMPARE(rects.front().topLeft(), bounds.topLeft());
        for (std::size_t i = 1; i < rects.size(); ++i)
        {
            const QRectF& prev = rects[i - 1];
            const QRectF& cur = rects[i];
            const bool sameRow = std::abs(cur.top() - prev.top()) < 1e-9;
            if (sameRow)
            {
                QVERIFY(std::abs(cur.left() - prev.right()) < 1e-9);
            }
            else
            {
                QVERIFY(std::abs(cur.top() - prev.bottom()) < 1e-9);
                QCOMPARE(cur.left(), bounds.left());
            }
        }

        // Tall bounds: the same, turned into columns placed left to right.
        const std::vector<QRectF> tall = layoutRows(sizes, QRectF(0, 0, 200, 400));
        QCOMPARE(tall.front().topLeft(), QPointF(0, 0));
        QVERIFY(tall[1].top() >= tall[0].bottom() - 1e-9 || tall[1].left() >= tall[0].right() - 1e-9);
        QCOMPARE(tall.back().right(), 200.0);
    }

    void rowsKeepCellsFromGettingTooNarrow()
    {
        // Every cell after the first in its row is at least 0.4 times as wide
        // as the row is thick; the first is wider still.
        std::vector<qint64> sizes;
        for (int i = 60; i > 0; --i)
        {
            sizes.push_back(i * i);
        }
        const std::vector<QRectF> rects = layoutRows(sizes, QRectF(0, 0, 800, 500));
        for (const QRectF& r : rects)
        {
            QVERIFY2(r.width() >= 0.4 * r.height() - 1e-6,
                     qPrintable(QStringLiteral("%1x%2").arg(r.width()).arg(r.height())));
        }
    }

    void rowsHandleDegenerateInput()
    {
        QVERIFY(layoutRows({}, QRectF(0, 0, 10, 10)).empty());
        const auto rects = layoutRows({1, 2}, QRectF(0, 0, 0, 10));
        QCOMPARE(rects.size(), std::size_t(2));
        QVERIFY(rects[0].isNull());
    }

    void layoutLeavesTileTheBounds()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        SizeNode* drive = root.addFolder(QStringLiteral("Cloud Drive"));
        SizeNode* photos = drive->addFolder(QStringLiteral("Photos"));
        for (int i = 1; i <= 20; ++i)
        {
            photos->addFile(QStringLiteral("p%1.jpg").arg(i), i * 1000);
        }
        drive->addFile(QStringLiteral("video.mp4"), 90000);
        drive->addFile(QStringLiteral("zero.txt"), 0);
        drive->addFolder(QStringLiteral("empty"));
        root.addFolder(QStringLiteral("Rubbish Bin"))->addFile(QStringLiteral("x.bin"), 5000);
        finalizeTree(root);

        const QRectF bounds(0, 0, 640, 480);
        const std::vector<TreemapCell> cells = layoutTreemap(root, bounds);
        QVERIFY(!cells.empty());
        QCOMPARE(cells.front().node, &root);
        QCOMPARE(cells.front().depth, 0);

        double leafArea = 0;
        int leaves = 0;
        for (const TreemapCell& cell : cells)
        {
            QVERIFY(cell.node->size > 0);
            QVERIFY(inside(cell.rect, bounds));
            if (cell.leaf)
            {
                ++leaves;
                leafArea += area(cell.rect);
                QVERIFY(!cell.node->isFolder());
            }
            if (cell.node->parent && cell.node != &root)
            {
                // Pre-order: the parent's cell comes first and contains the child.
                const auto parentIt =
                    std::find_if(cells.begin(), cells.end(), [&](const TreemapCell& c) {
                        return c.node == cell.node->parent;
                    });
                QVERIFY(parentIt != cells.end());
                QVERIFY(parentIt < cells.end() && &*parentIt < &cell);
                QVERIFY(inside(cell.rect, parentIt->rect));
                QCOMPARE(cell.depth, parentIt->depth + 1);
            }
        }
        QCOMPARE(leaves, 22);
        QVERIFY(std::abs(leafArea - area(bounds)) < 1e-6 * area(bounds));
    }

    void tinyFoldersBecomeLeaves()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        root.addFile(QStringLiteral("huge.bin"), 1'000'000'000);
        SizeNode* folder = root.addFolder(QStringLiteral("tiny"));
        folder->addFile(QStringLiteral("a"), 1);
        folder->addFile(QStringLiteral("b"), 1);
        finalizeTree(root);

        const std::vector<TreemapCell> cells = layoutTreemap(root, QRectF(0, 0, 100, 100));
        const auto it = std::find_if(cells.begin(), cells.end(), [&](const TreemapCell& c) {
            return c.node == folder;
        });
        QVERIFY(it != cells.end());
        QVERIFY(it->leaf);
        QVERIFY(std::none_of(cells.begin(), cells.end(), [&](const TreemapCell& c) {
            return c.node->parent == folder;
        }));
    }

    void smallChildrenAreMergedIntoOneCell()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        SizeNode* big = root.addFile(QStringLiteral("big"), 9000);
        for (int i = 0; i < 10; ++i)
        {
            root.addFile(QStringLiteral("s%1").arg(i), 100);
        }
        finalizeTree(root);

        // 100x100 bounds: each small file would get 100 px^2, below 256.
        TreemapOptions options;
        options.minArea = 256;
        const std::vector<TreemapCell> cells = layoutTreemap(root, QRectF(0, 0, 100, 100), options);
        QCOMPARE(cells.size(), std::size_t(3));
        QCOMPARE(cells[1].node, big);
        QVERIFY(!cells[1].isAggregate());

        const TreemapCell& merged = cells[2];
        QVERIFY(merged.isAggregate());
        QVERIFY(merged.leaf);
        QCOMPARE(merged.node, &root);
        QCOMPARE(merged.aggregatedCount, 10);
        QCOMPARE(merged.aggregatedSize, 1000);
        QVERIFY(std::abs(area(merged.rect) - 1000.0) < 1e-6);
        QVERIFY(std::abs(area(cells[1].rect) + area(merged.rect) - 10000.0) < 1e-6);
    }

    void thinChildrenAreMergedEvenAboveMinArea()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        root.addFile(QStringLiteral("big"), 9400);
        root.addFile(QStringLiteral("a"), 300);
        root.addFile(QStringLiteral("b"), 300);
        finalizeTree(root);

        // a and b get 300 px^2 each (above 256) but only as 6x50 slivers.
        TreemapOptions options;
        options.minSide = 16;
        options.minArea = 256;
        const std::vector<TreemapCell> cells = layoutTreemap(root, QRectF(0, 0, 100, 100), options);
        QCOMPARE(cells.size(), std::size_t(3));
        QVERIFY(cells[2].isAggregate());
        QCOMPARE(cells[2].aggregatedCount, 2);
        QCOMPARE(cells[2].aggregatedSize, 600);
    }

    void singleSmallChildIsNotMerged()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        root.addFile(QStringLiteral("big"), 9900);
        SizeNode* small = root.addFile(QStringLiteral("small"), 100);
        finalizeTree(root);

        TreemapOptions options;
        options.minArea = 256;
        const std::vector<TreemapCell> cells = layoutTreemap(root, QRectF(0, 0, 100, 100), options);
        QCOMPARE(cells.size(), std::size_t(3));
        QCOMPARE(cells[2].node, small);
        QVERIFY(!cells[2].isAggregate());
    }

    void folderOfOnlySmallChildrenIsOneCell()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        root.addFile(QStringLiteral("big"), 1'000'000);
        SizeNode* folder = root.addFolder(QStringLiteral("f"));
        for (int i = 0; i < 5; ++i)
        {
            folder->addFile(QStringLiteral("s%1").arg(i), 10'000);
        }
        finalizeTree(root);

        // The folder gets ~4760 px^2 and is wide enough to subdivide, but every
        // child (~950 px^2) is below minArea.
        TreemapOptions options;
        options.minArea = 1000;
        const std::vector<TreemapCell> cells = layoutTreemap(root, QRectF(0, 0, 1000, 100), options);
        const auto it = std::find_if(cells.begin(), cells.end(), [&](const TreemapCell& c) {
            return c.node == folder;
        });
        QVERIFY(it != cells.end());
        QVERIFY(it->leaf);
        QVERIFY(!it->isAggregate());
        QVERIFY(std::none_of(cells.begin(), cells.end(), [&](const TreemapCell& c) {
            return c.node->parent == folder;
        }));
    }
};

QTEST_GUILESS_MAIN(TestTreemapLayout)
#include "tst_treemaplayout.moc"
