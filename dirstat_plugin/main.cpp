#include "plugin/PluginHost.h"
#include "plugin/RpcChannel.h"

#include <QApplication>
#include <QIcon>
#include <QMessageBox>

#include <cstdio>

namespace
{

// stderr is a pipe into MEGA Explorer's log. Qt's default handler sends a GUI
// process's output to OutputDebugString instead, so write it there by hand.
void logToStderr(QtMsgType type, const QMessageLogContext& context, const QString& message)
{
    static const char* const kLevels[] = {"debug", "warning", "critical", "fatal", "info"};
    const QByteArray text = message.toUtf8();
    std::fprintf(stderr,
                 "%s: [%s] %s\n",
                 kLevels[type],
                 context.category ? context.category : "default",
                 text.constData());
    std::fflush(stderr);
}

} // namespace

int main(int argc, char* argv[])
{
    qInstallMessageHandler(logToStderr);
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("MegaDirStat"));
    // The run ends with the app's shutdown request, not with the window.
    QApplication::setQuitOnLastWindowClosed(false);

    {
        QIcon windowIcon;
        for (int size : {16, 24, 32, 48, 64, 256})
        {
            windowIcon.addFile(QStringLiteral(":/resources/appicon-%1.png").arg(size));
        }
        QApplication::setWindowIcon(windowIcon);
    }

    if (!RpcChannel::isConnected())
    {
        QMessageBox::information(
            nullptr,
            QStringLiteral("MegaDirStat"),
            QObject::tr("This is a MEGA Explorer plugin. Right-click a folder in MEGA Explorer "
                        "and choose MegaDirStat to open it."));
        return 1;
    }

    RpcChannel rpc;
    PluginHost host(rpc);
    rpc.start();
    return app.exec();
}
