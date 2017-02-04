from os import path
from glob import glob

import cv2
import tensorflow as tf
import numpy as np

from libs import import_images, VAE


def normalize_img(img):
    min, max = img.min(), img.max()
    return (img - min) / (max - min)


def example_gallery(Xs, reconstructed):
    if np.isnan(reconstructed).any():
        print('Warning: NaN value detected in reconstruction.')

    org = Xs[0, :, :, :]
    img = reconstructed[0, :, :, :]
    img = normalize_img(img)
    canvas_left = np.concatenate((org, img), axis=0)

    org = Xs[1, :, :, :]
    img = reconstructed[1, :, :, :]
    img = normalize_img(img)
    canvas_right = np.concatenate((org, img), axis=0)

    return np.concatenate((canvas_left, canvas_right), axis=1)


def main():
    window = 'preview'
    cv2.namedWindow(window)

    tfrecord_file_names = glob(path.join('data', '*.tfrecord.gz'))
    max_reads = 200
    batch_size = 100

    n_epochs = 50
    keep_prob = 0.8
    n_code = 128
    learning_rate = 5e-2
    img_step = 20

    with tf.Graph().as_default() as graph:
        image_batch, type_batch = import_images(tfrecord_file_names, max_reads=max_reads, batch_size=batch_size)

        with tf.variable_scope('vae'):
            ae = VAE(input_shape=(None, 180, 320, 3),
                     convolutional=True,
                     variational=True,
                     n_filters=[16, 32, 64, 256],
                     filter_sizes=[7, 5, 3, 3],
                     n_hidden=192,
                     n_code=n_code,
                     dropout=False,
                     activation=tf.nn.elu)
            loss = ae['cost']

        with tf.variable_scope('training'):
            optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(loss)

    coord = tf.train.Coordinator()
    with tf.Session(graph=graph) as sess:
        init = tf.group(tf.local_variables_initializer(), tf.global_variables_initializer())
        sess.run(init)

        threads = tf.train.start_queue_runners(sess=sess, coord=coord)

        try:
            batch_i = 0
            epoch_i = 0

            print('Loading test data ...')
            test_Xs = np.array([cv2.imread(path.join('test', 'test_1.jpg')),
                                cv2.imread(path.join('test', 'test_2.jpg'))], np.float32) / 255.

            if False:
                print('Initial evaluation.')
                reconstructed = sess.run(ae['y'], feed_dict={ae['x']: test_Xs,
                                                             ae['train']: False,
                                                             ae['keep_prob']: 1.0})

                canvas = example_gallery(test_Xs, reconstructed)
                cv2.imshow(window, canvas)

            while not coord.should_stop() and epoch_i < n_epochs:
                batch_i += 1

                Xs = sess.run(image_batch)
                train_loss, _ = sess.run([ae['cost'], optimizer],
                                         feed_dict={ae['x']: Xs,
                                                    ae['train']: True,
                                                    ae['keep_prob']: keep_prob})

                # current batch and mini-batch training loss
                print(batch_i, train_loss)

                if batch_i % img_step == 0:
                    print('Evaluating at batch {0:d}.'.format(batch_i))
                    reconstructed = sess.run(ae['y'], feed_dict={ae['x']: test_Xs,
                                                                 ae['train']: False,
                                                                 ae['keep_prob']: 1.0})

                    canvas = example_gallery(test_Xs, reconstructed)
                    cv2.imshow(window, canvas)

                # display responsiveness
                if (cv2.waitKey(1) & 0xff) == 27:
                    coord.request_stop()
                    break


        except tf.errors.OutOfRangeError:
            print('Read all examples.')
        finally:
            coord.request_stop()
            coord.join(threads)

        cv2.destroyWindow(window)


if __name__ == '__main__':
    main()
